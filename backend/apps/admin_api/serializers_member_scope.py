from rest_framework import serializers


class AssignableMachineTypeSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    name = serializers.CharField()
    slug = serializers.CharField()
    is_global = serializers.BooleanField()


class MemberMachineScopeSerializer(serializers.Serializer):
    membership_id = serializers.IntegerField()
    scoping_applies = serializers.BooleanField()
    machine_type_ids = serializers.ListField(child=serializers.IntegerField())
    available_machine_types = AssignableMachineTypeSerializer(many=True)


class MemberMachineScopeWriteSerializer(serializers.Serializer):
    machine_type_ids = serializers.ListField(child=serializers.IntegerField(min_value=1))

    def validate_machine_type_ids(self, value):
        if len(set(value)) != len(value):
            raise serializers.ValidationError("Duplicate machine type ids are not allowed.")
        return value
