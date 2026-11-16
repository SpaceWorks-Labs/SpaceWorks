from django.db import migrations, models
import apps.makerspaces.loan_context_generations


def seed_generations(registry, schema_editor):
    space = registry.get_model("makerspaces", "Makerspace")
    alias = schema_editor.connection.alias
    for pk in space.objects.using(alias).values_list("pk", flat=True).iterator():
        space.objects.using(alias).filter(pk=pk).update(
            loan_context_generations=apps.makerspaces.loan_context_generations.new_generations())


class Migration(migrations.Migration):
    dependencies = [("makerspaces", "0133_makerspace_public_stats_config")]
    operations = [
        migrations.AddField(model_name="makerspace", name="loan_context_generations",
            field=models.JSONField(null=True, editable=False)),
        migrations.RunPython(seed_generations, migrations.RunPython.noop),
        migrations.AlterField(model_name="makerspace", name="loan_context_generations",
            field=models.JSONField(default=apps.makerspaces.loan_context_generations.new_generations,
                editable=False, validators=[apps.makerspaces.loan_context_generations.validate_generations])),
    ]
