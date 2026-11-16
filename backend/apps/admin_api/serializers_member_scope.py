from django.utils.translation import gettext
from rest_framework import serializers


class AssignableMachineTypeSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    name = serializers.CharField()
    slug = serializers.CharField()
    is_global = serializers.BooleanField()


class AssignableMachineSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    name = serializers.CharField()
    machine_type_id = serializers.IntegerField()


class MemberMachineScopeSerializer(serializers.Serializer):
    membership_id = serializers.IntegerField()
    scoping_applies = serializers.BooleanField()
    machine_type_ids = serializers.ListField(child=serializers.IntegerField())
    machine_ids = serializers.ListField(child=serializers.IntegerField())
    available_machine_types = AssignableMachineTypeSerializer(many=True)
    available_machines = AssignableMachineSerializer(many=True)


class MemberMachineScopeWriteSerializer(serializers.Serializer):
    machine_type_ids = serializers.ListField(child=serializers.IntegerField(min_value=1), required=False)
    machine_ids = serializers.ListField(child=serializers.IntegerField(min_value=1), required=False)

    def validate_machine_type_ids(self, value):
        if len(set(value)) != len(value):
            raise serializers.ValidationError(gettext("Duplicate machine type ids are not allowed."))
        return value

    def validate_machine_ids(self, value):
        if len(set(value)) != len(value):
            raise serializers.ValidationError(gettext("Duplicate machine ids are not allowed."))
        return value

    def validate(self, attrs):
        if not attrs:
            raise serializers.ValidationError(gettext("Provide machine_type_ids or machine_ids."))
        return attrs
