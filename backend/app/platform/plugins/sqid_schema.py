from litestar.openapi.spec import OpenAPIType, Schema
from litestar.plugins import OpenAPISchemaPlugin

from app.utils.sqids import Sqid


class SqidSchemaPlugin(OpenAPISchemaPlugin):
    @staticmethod
    def is_plugin_supported_type(value: object) -> bool:
        return value is Sqid

    def to_openapi_schema(self, field_definition: object, schema_creator: object) -> Schema:
        return Schema(
            type=OpenAPIType.STRING,
            description="SQID-encoded identifier",
            example="kmxpqdrv",
        )
