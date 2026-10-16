from django.contrib import admin



from .models import MarcoCalendario


@admin.register(MarcoCalendario)
class MarcoCalendarioAdmin(admin.ModelAdmin):
    list_display = ("semestre", "tipo", "data_limite", "alterado_por", "alterado_em")
    list_filter = ("tipo", "semestre")
    search_fields = ("semestre",)
    ordering = ("-semestre", "tipo")
    readonly_fields = ("alterado_por", "alterado_em")
   
    def save_model(self, request, obj, form, change):
        obj.alterado_por = request.user
        super().save_model(request, obj, form, change)