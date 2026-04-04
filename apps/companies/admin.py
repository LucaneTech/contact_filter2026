from django.contrib import admin
from .models import Company, UploadedFile, ProcessingHistory


@admin.register(Company)
class CompanyAdmin(admin.ModelAdmin):
    list_display = ('name', 'user', 'subscription_status', 'monthly_quota', 'contacts_used_this_month')
    list_filter = ('subscription_status',)
    search_fields = ('name', 'user__email')


@admin.register(UploadedFile)
class UploadedFileAdmin(admin.ModelAdmin):
    list_display = ('original_name', 'company', 'status', 'progress', 'rows_original', 'created_at', 'expires_at')
    list_filter = ('status',)


@admin.register(ProcessingHistory)
class ProcessingHistoryAdmin(admin.ModelAdmin):
    list_display = ('original_filename', 'company', 'rows_original', 'rows_after_filter','created_at', 'expires_at')
