from django.db import migrations, models
from pgvector.django import VectorExtension, VectorField


class Migration(migrations.Migration):
    """
    Additive-only. Enables pgvector and adds two nullable columns to document_chunks.
    No data is read, rewritten or deleted. No index is created.
    """

    dependencies = [
        ("rag", "0001_initial"),
    ]

    operations = [
        VectorExtension(),
        migrations.AddField(
            model_name="documentchunk",
            name="embedding",
            field=VectorField(
                blank=True,
                dimensions=768,
                editable=False,
                help_text="768-dimensional embedding (Nomic Embed Text v1.5); cosine distance is used for retrieval.",
                null=True,
            ),
        ),
        migrations.AddField(
            model_name="documentchunk",
            name="embedding_updated_at",
            field=models.DateTimeField(
                blank=True,
                help_text="When the pgvector embedding was written or verified.",
                null=True,
            ),
        ),
    ]
