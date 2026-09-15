from drf_spectacular.utils import OpenApiParameter, OpenApiTypes, extend_schema
from rest_framework import serializers, status
from rest_framework.parsers import FormParser, MultiPartParser
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from .data_io import execute_import, export_rows, parse_mapping, parse_uploaded_table, prepare_import, tabular_response
from .data_resources import get_data_resource


class DataImportRequestSerializer(serializers.Serializer):
    resource = serializers.CharField(max_length=160)
    file = serializers.FileField()
    mapping = serializers.JSONField()
    mode = serializers.ChoiceField(choices=("create", "update", "upsert", "skip_duplicates"), default="create")
    commit = serializers.BooleanField(default=False)


class DataImportResultSerializer(serializers.Serializer):
    resource = serializers.CharField()
    mode = serializers.CharField()
    commit = serializers.BooleanField()
    counts = serializers.JSONField()
    errors = serializers.JSONField()
    preview = serializers.JSONField()
    result = serializers.JSONField(required=False)


class DataImportView(APIView):
    permission_classes = [IsAuthenticated]
    parser_classes = [MultiPartParser, FormParser]
    serializer_class = DataImportRequestSerializer

    @extend_schema(request=DataImportRequestSerializer, responses=DataImportResultSerializer)
    def post(self, request):
        resource = str(request.data.get("resource", "")).strip()
        if not resource:
            return Response({"resource": ["This field is required."]}, status=status.HTTP_400_BAD_REQUEST)
        upload = request.FILES.get("file")
        if upload is None:
            return Response({"file": ["This field is required."]}, status=status.HTTP_400_BAD_REQUEST)
        mapping = parse_mapping(request.data.get("mapping"))
        mode = str(request.data.get("mode", "create"))
        commit_value = request.data.get("commit", False)
        commit = commit_value is True or str(commit_value).lower() in {"1", "true", "yes", "on"}
        rows = parse_uploaded_table(upload)
        plans = prepare_import(request=request, model_key=resource, rows=rows, mapping=mapping, mode=mode)
        errors = [{"row": plan["row"], "errors": plan["errors"]} for plan in plans if plan.get("errors")]
        counts = {
            "rows": len(plans),
            "valid": len(plans) - len(errors),
            "errors": len(errors),
            "create": sum(plan.get("action") == "create" for plan in plans),
            "update": sum(plan.get("action") == "update" for plan in plans),
            "skip": sum(plan.get("action") == "skip" for plan in plans),
        }
        response = {
            "resource": resource,
            "mode": mode,
            "commit": False,
            "counts": counts,
            "errors": errors[:200],
            "preview": [
                {"row": plan["row"], "action": plan.get("action"), "data": plan.get("native", {}), "custom": plan.get("custom", {})}
                for plan in plans[:20]
            ],
        }
        if commit:
            if errors:
                return Response(response, status=status.HTTP_400_BAD_REQUEST)
            response["result"] = execute_import(request=request, model_key=resource, plans=plans)
            response["commit"] = True
        return Response(response)


class DataExportView(APIView):
    permission_classes = [IsAuthenticated]
    serializer_class = serializers.Serializer

    @extend_schema(
        parameters=[
            OpenApiParameter("resource", OpenApiTypes.STR, OpenApiParameter.QUERY, required=True),
            OpenApiParameter("output_format", OpenApiTypes.STR, OpenApiParameter.QUERY, required=False, enum=["csv", "xlsx"]),
            OpenApiParameter("fields", OpenApiTypes.STR, OpenApiParameter.QUERY, required=False),
        ],
        responses={200: OpenApiTypes.BINARY},
    )
    def get(self, request):
        resource = str(request.query_params.get("resource", "")).strip()
        if not resource:
            return Response({"resource": ["This query parameter is required."]}, status=status.HTTP_400_BAD_REQUEST)
        try:
            adapter = get_data_resource(resource)
        except LookupError as exc:
            return Response({"resource": [str(exc)]}, status=status.HTTP_400_BAD_REQUEST)
        requested = str(request.query_params.get("fields", "")).strip()
        fields = [item.strip() for item in requested.split(",") if item.strip()] if requested else list(adapter.export_fields)
        output_format = str(request.query_params.get("output_format", "csv")).lower()
        rows = export_rows(request=request, model_key=resource, fields=fields)
        filename = resource.replace(".", "-") + "-export"
        return tabular_response(headers=fields, rows=rows, output_format=output_format, filename=filename)
