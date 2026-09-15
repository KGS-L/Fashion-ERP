from django.db import transaction
from django.utils import timezone
from rest_framework import generics,status
from rest_framework.exceptions import PermissionDenied,ValidationError
from rest_framework.permissions import IsAuthenticated
from rest_framework.views import APIView
from rest_framework.response import Response
from ivadoo.audit.services import audit_snapshot,record_audit_event
from ivadoo.authorization.services import authorized_company_ids,has_permission
from .models import Order,Quotation
from .serializers import OrderSerializer,QuotationSerializer

def scoped(model,user,perm): return model.objects.filter(organization_id=user.organization_id,company_id__in=authorized_company_ids(user,perm))
class QuotationListCreateView(generics.ListCreateAPIView):
    queryset=Quotation.objects.none(); serializer_class=QuotationSerializer; permission_classes=[IsAuthenticated]; filterset_fields=("company_id","customer_id","status"); search_fields=("number","customer__display_name")
    def get_queryset(self): return scoped(Quotation,self.request.user,"fashion.sale.view").prefetch_related("lines")
    def perform_create(self,s):
        company=s.validated_data["company"]; customer=s.validated_data["customer"]
        if customer.company_id!=company.id or not has_permission(self.request.user,"fashion.sale.manage",company=company): raise PermissionDenied()
        q=s.save(organization=self.request.user.organization); record_audit_event(organization=self.request.user.organization,actor=self.request.user,action="fashion.quotation.create",object_instance=q,request=self.request)
class OrderListCreateView(generics.ListCreateAPIView):
    queryset=Order.objects.none(); serializer_class=OrderSerializer; permission_classes=[IsAuthenticated]; filterset_fields=("company_id","customer_id","status"); search_fields=("number","customer__display_name")
    def get_queryset(self): return scoped(Order,self.request.user,"fashion.sale.view").prefetch_related("lines")
    def perform_create(self,s):
        company=s.validated_data["company"]; customer=s.validated_data["customer"]
        if customer.company_id!=company.id or not has_permission(self.request.user,"fashion.sale.manage",company=company): raise PermissionDenied()
        s.save(organization=self.request.user.organization)

class QuotationActionView(APIView):
    permission_classes=[IsAuthenticated]
    serializer_class=QuotationSerializer
    def post(self,request,quotation_id,action):
        if action not in {"send","accept","reject","expire"}: return Response(status=status.HTTP_404_NOT_FOUND)
        q=scoped(Quotation,request.user,"fashion.sale.manage").get(id=quotation_id)
        allowed={"send":("draft","sent"),"accept":("sent","accepted"),"reject":("sent","rejected"),"expire":("sent","expired")}
        source,dest=allowed[action]
        if q.status!=source: raise ValidationError({"status":f"Cannot {action} quotation from {q.status}."})
        q.status=dest;q.save(update_fields=["status","updated_at"])
        record_audit_event(organization=request.user.organization,actor=request.user,action=f"fashion.quotation.{action}",object_instance=q,request=request)
        return Response(QuotationSerializer(q).data)

class OrderActionView(APIView):
    permission_classes=[IsAuthenticated]
    serializer_class=OrderSerializer
    def post(self,request,order_id,action):
        with transaction.atomic():
            o=scoped(Order,request.user,"fashion.sale.manage").select_for_update().prefetch_related("lines__measurement_set__values__definition").get(id=order_id)
            if action=="confirm":
                if o.status!="draft": raise ValidationError({"status":"Only draft orders can be confirmed."})
                for line in o.lines.all():
                    ms=line.measurement_set
                    if ms:
                        line.measurement_snapshot={"measurement_set_id":str(ms.id),"version":ms.version,"measured_at":ms.measured_at.isoformat(),"values":[{"definition_id":str(v.definition_id),"code":v.definition.code,"value":str(v.value),"tolerance":str(v.tolerance) if v.tolerance is not None else None,"note":v.note} for v in ms.values.all()]};line.measurement_source_version=ms.version;line.save(update_fields=["measurement_snapshot","measurement_source_version"])
                o.status="confirmed";o.confirmed_at=timezone.now();o.save(update_fields=["status","confirmed_at","updated_at"])
            elif action=="cancel":
                if o.status=="cancelled": raise ValidationError({"status":"Order is already cancelled."})
                o.status="cancelled";o.cancelled_at=timezone.now();o.save(update_fields=["status","cancelled_at","updated_at"])
            else:return Response(status=status.HTTP_404_NOT_FOUND)
            record_audit_event(organization=request.user.organization,actor=request.user,action=f"fashion.order.{action}",object_instance=o,request=request)
            return Response(OrderSerializer(o).data)
