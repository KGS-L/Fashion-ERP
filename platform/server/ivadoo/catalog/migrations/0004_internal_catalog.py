from django.db import migrations,models
class Migration(migrations.Migration):
 dependencies=[("catalog","0003_model_material_requirements")]
 operations=[migrations.AddField(model_name="product",name="is_internal_published",field=models.BooleanField(default=False)),migrations.AddField(model_name="product",name="commercial_status",field=models.CharField(default="available",max_length=24)),migrations.AddField(model_name="product",name="list_price",field=models.DecimalField(blank=True,decimal_places=4,max_digits=14,null=True))]
