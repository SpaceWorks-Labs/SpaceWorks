"""The control plane creates platform principals; it never promotes community users."""

from django import forms
from unfold.forms import UserChangeForm, UserCreationForm

from .models import User
from .staff_identity import PLATFORM_KIND, is_platform
from django.utils.translation import gettext


class PlatformUserCreationForm(UserCreationForm):
    class Meta(UserCreationForm.Meta):
        model = User

    def clean(self):
        cleaned = super().clean()
        self.instance.account_kind = PLATFORM_KIND
        self.instance.is_superuser = True
        self.instance.is_staff = True
        self.instance.role = User.Role.SUPERADMIN
        return cleaned


class AccountUserChangeForm(UserChangeForm):
    class Meta(UserChangeForm.Meta):
        model = User

    def clean(self):
        cleaned = super().clean()
        original = User.objects.get(pk=self.instance.pk)
        is_superuser = cleaned.get("is_superuser", original.is_superuser)
        role = cleaned.get("role", original.role)
        platform = is_platform(original)
        if is_superuser != platform or (role == User.Role.SUPERADMIN) != platform:
            raise forms.ValidationError(gettext("Create a separate platform account; account kinds cannot be changed."))
        return cleaned
