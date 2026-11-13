"""Typed organization editorial history; NULL construction shells never publish."""
import uuid
from django.conf import settings
from django.db import migrations, models
from apps.makerspaces.migrations._public_page_guards import sql, reverse_sql


class Migration(migrations.Migration):
    dependencies = [('organizations', '0004_organization_is_discoverable'), ('makerspaces', '0100_public_pages'), migrations.swappable_dependency(settings.AUTH_USER_MODEL)]
    operations = [
        migrations.CreateModel(name='OrganizationPublicPage', fields=[
            ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
            ('version', models.PositiveIntegerField(default=0)),
            ('organization', models.OneToOneField('organizations.organization', on_delete=models.CASCADE, related_name='public_page')),
        ]),
        migrations.CreateModel(name='OrganizationPublicPageRevision', fields=[
            ('id', models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False, serialize=False)),
            ('schema_version', models.PositiveSmallIntegerField(default=1)),
            ('created_at', models.DateTimeField(auto_now_add=True)),
            ('document', models.JSONField()),
            ('created_by', models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name='+')),
            ('page', models.ForeignKey('organizations.organizationpublicpage', on_delete=models.CASCADE, related_name='revisions')),
        ]),
        migrations.AddField(model_name='organizationpublicpage', name='draft_revision', field=models.ForeignKey(
            'organizations.organizationpublicpagerevision', null=True, blank=True, on_delete=models.SET_NULL, related_name='+')),
        migrations.AddField(model_name='organizationpublicpage', name='published_revision', field=models.ForeignKey(
            'organizations.organizationpublicpagerevision', null=True, blank=True, on_delete=models.SET_NULL, related_name='+')),
        migrations.CreateModel(name='OrganizationPublicPageAsset', fields=[
            ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
            ('object_key', models.CharField(max_length=300, unique=True)),
            ('size_bytes', models.PositiveIntegerField()),
            ('alt_text', models.CharField(max_length=200)),
            ('created_at', models.DateTimeField(auto_now_add=True)),
            ('page', models.ForeignKey('organizations.organizationpublicpage', on_delete=models.CASCADE, related_name='assets')),
        ]),
        migrations.CreateModel(name='OrganizationPublicPageRevisionAsset', fields=[
            ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
            ('slot', models.CharField(max_length=80)),
            ('revision', models.ForeignKey('organizations.organizationpublicpagerevision', on_delete=models.CASCADE, related_name='asset_references')),
            ('asset', models.ForeignKey('organizations.organizationpublicpageasset', on_delete=models.RESTRICT)),
        ], options={'constraints': [models.UniqueConstraint(fields=('revision', 'slot'), name='org_page_asset_slot')]}),
        migrations.CreateModel(name='OrganizationPublicPageRevisionMember', fields=[
            ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
            ('slot', models.UUIDField()),
            ('revision', models.ForeignKey('organizations.organizationpublicpagerevision', on_delete=models.CASCADE, related_name='member_references')),
            ('profile', models.ForeignKey('makerspaces.memberprofile', null=True, on_delete=models.SET_NULL)),
        ], options={'constraints': [models.UniqueConstraint(fields=('revision', 'slot'), name='org_page_member_slot')]}),
        migrations.RunSQL(sql('organizations', 'organizationpublicpage'), reverse_sql('organizations', 'organizationpublicpage')),
    ]
    operations.append(migrations.CreateModel(name='OrganizationPublicPageStorage', fields=[
        ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
        ('used_bytes', models.PositiveBigIntegerField(default=0)),
        ('organization', models.OneToOneField('organizations.organization', on_delete=models.CASCADE, related_name='page_storage')),
    ]))
