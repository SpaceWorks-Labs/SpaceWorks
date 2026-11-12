"""Avatar and project image upload/attach/clear for the caller's own account profile.

Mirrors `events.views_admin_image` step for step, including the order of the checks: the
prefix test runs before anything touches storage, because it is what stops a member attaching
an object minted for a space they do not belong to.

One endpoint set serves both the avatar and a project image, discriminated by an optional
`project_id`. Two near-identical triples would have been two places to forget the
key-collision check.
"""

from django.utils.translation import gettext
from drf_spectacular.utils import OpenApiResponse, extend_schema
from rest_framework import serializers, status
from rest_framework.exceptions import ValidationError
from rest_framework.response import Response

from apps.admin_api.serializers_inventory import (
    PublicImageAttachRequestSerializer,
    PublicImageUploadRequestSerializer,
    PublicImageUploadResponseSerializer,
)
from apps.evidence.responses import storage_unavailable_response
from apps.evidence.storage import StorageUnavailable
from apps.inventory import public_image_storage
from apps.makerspaces import profile_images
from apps.makerspaces.models import MakerspaceMembership
from apps.makerspaces.account_profile import account_profile_for
from apps.makerspaces.account_profile_read import build_payload
from apps.makerspaces.account_profile_serializers import AccountProfileSerializer
from apps.makerspaces.account_profile_views import AccountOwnerView
from apps.makerspaces.throttles import MemberImagePresignThrottle

IMAGE_KIND = profile_images.IMAGE_KIND


class ProfileImageUploadRequestSerializer(PublicImageUploadRequestSerializer):
    project_id = serializers.IntegerField(required=False)


class ProfileImageAttachRequestSerializer(PublicImageAttachRequestSerializer):
    project_id = serializers.IntegerField(required=False)


class AccountProfileImageView(AccountOwnerView):
    # The throttle is a no-op on PUT and DELETE by construction -- see the class -- so
    # declaring it on the view budgets the presign alone.
    throttle_classes = [MemberImagePresignThrottle]

    def _project(self, profile, project_id):
        if project_id is None:
            return None
        project = profile.projects.filter(pk=project_id).first()
        if project is None:
            # 400 rather than 404: the profile exists and is the caller's, so this is a
            # bad field in their payload, not a missing resource.
            raise ValidationError({"project_id": gettext("Unknown project.")})
        return project

    @extend_schema(
        tags=["Member profile"],
        summary="Create a profile image upload URL",
        request=ProfileImageUploadRequestSerializer,
        responses={
            201: PublicImageUploadResponseSerializer,
            400: OpenApiResponse(description="Invalid image upload request."),
            429: OpenApiResponse(description="Too many image upload requests."),
            503: OpenApiResponse(description="Public image storage is unavailable."),
        },
    )
    def post(self, request, **kwargs):
        user = self.actor(request, **kwargs)
        space = self.audit_space or profile_images.home_space(user)
        serializer = ProfileImageUploadRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        content_type = serializer.validated_data["content_type"]
        ext = public_image_storage.ext_for(
            content_type, serializer.validated_data["filename"]
        )
        if space is None:
            # No active membership: mint in the account namespace, charged to no space.
            object_key = public_image_storage.build_object_key(
                profile_images.ACCOUNT_KIND, user.pk, ext
            )
        else:
            object_key = public_image_storage.build_object_key(IMAGE_KIND, space.pk, ext)
        try:
            upload = public_image_storage.presigned_upload(object_key, content_type)
        except StorageUnavailable:
            return storage_unavailable_response()
        return Response(
            PublicImageUploadResponseSerializer({"object_key": object_key, **upload}).data,
            status=status.HTTP_201_CREATED,
        )

    @extend_schema(
        tags=["Member profile"],
        summary="Attach an uploaded image to the profile or one of its projects",
        request=ProfileImageAttachRequestSerializer,
        responses={
            200: AccountProfileSerializer,
            400: OpenApiResponse(description="Invalid image object key or size."),
            503: OpenApiResponse(description="Public image storage is unavailable."),
        },
    )
    def put(self, request, **kwargs):
        user = self.actor(request, **kwargs)
        serializer = ProfileImageAttachRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        object_key = serializer.validated_data["object_key"]
        profile = account_profile_for(user)
        project = self._project(profile, serializer.validated_data.get("project_id"))

        key_space = profile_images.space_for_key(object_key)
        own_account_key = object_key.startswith(profile_images.account_key_prefix(user))
        if not own_account_key and (key_space is None or not MakerspaceMembership.all_tracks.filter(
            user=user, status="active", makerspace=key_space,
        ).exists()):
            raise ValidationError(
                {"object_key": gettext("Image object key is outside your makerspaces.")}
            )
        if not public_image_storage.is_safe_object_key(object_key):
            raise ValidationError({"object_key": gettext("Invalid image object key.")})
        if public_image_storage.public_image_key_in_use(
            key_space.pk if key_space else 0,
            object_key,
            account_profile_id=None if project else profile.pk,
            account_project_id=project.pk if project else None,
        ):
            raise ValidationError({"object_key": gettext("This image is already in use.")})
        try:
            result = public_image_storage.finalize_upload(object_key)
        except StorageUnavailable:
            return storage_unavailable_response()
        if result.status != "ok":
            if result.status in {"empty", "too_large"}:
                _discard(object_key)
            raise ValidationError(
                {"object_key": public_image_storage.finalize_error_message(result)}
            )
        try:
            is_valid_image = public_image_storage.sniff_is_valid_image(object_key)
        except StorageUnavailable:
            return storage_unavailable_response()
        if not is_valid_image:
            _discard(object_key)
            raise ValidationError({"object_key": gettext("Uploaded file is not a valid image.")})
        if project is not None:
            profile_images.set_project_image(profile, project, object_key, makerspace=self.audit_space)
        else:
            profile_images.set_avatar(profile, object_key, makerspace=self.audit_space)
        profile.refresh_from_db()  # `_swap` writes through a freshly locked row, so ours is stale
        return Response(AccountProfileSerializer(build_payload(profile, "owner")).data)

    @extend_schema(
        tags=["Member profile"],
        summary="Clear a profile or project image",
        responses={
            200: AccountProfileSerializer,
            400: OpenApiResponse(description="Unknown project."),
        },
    )
    def delete(self, request, **kwargs):
        user = self.actor(request, **kwargs)
        profile = account_profile_for(user)
        raw_project_id = request.query_params.get("project_id")
        project = None
        if raw_project_id is not None:
            # A malformed id must NOT degrade to "no project": that branch clears the
            # avatar, so `?project_id=abc` would destroy a different image than the one
            # the caller named. Present-but-unparseable is a 400.
            if not raw_project_id.isdigit():
                raise ValidationError({"project_id": gettext("Invalid project id.")})
            project = self._project(profile, int(raw_project_id))
        if project is not None:
            profile_images.clear_project_image(profile, project)
        elif profile.avatar_key:
            profile_images.set_avatar(profile, "", makerspace=self.audit_space)
        profile.refresh_from_db()  # `_swap` writes through a freshly locked row, so ours is stale
        return Response(AccountProfileSerializer(build_payload(profile, "owner")).data)


def _discard(object_key):
    public_image_storage.delete_object(object_key)
    public_image_storage.delete_object(public_image_storage.staging_key(object_key))
