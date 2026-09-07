"""AUTO-GENERATED — DO NOT EDIT.

Produced by ``python scripts/build_models.py``.
Regenerate whenever ``tools/workflow_reference/manifest.json`` changes.

Exports
-------
``TaskTypeEnum``
    Constrained list of every supported Zuora Workflow ``action_type``.
``TASK_TYPE_CONFIG_MAP``
    Maps ``action_type`` to its ``<TaskName>Parameters`` model (for
    parameters-dict validation via ``model_validate``).
``TASK_TYPE_TASK_MAP``
    Maps ``action_type`` to its full ``<TaskName>Task`` model.
``TaskUnion``
    Discriminated union of every task model; use for typed
    ``tasks: list[TaskUnion]`` on the workflow export.
``TASK_LINKAGE_TYPES``
    Valid outgoing linkage labels per task (``None`` = dynamic).
"""

from __future__ import annotations

from enum import Enum
from typing import Annotated, Union

from pydantic import BaseModel, Field

from .generated import (
    ApprovalTask,
    ApprovalTaskParameters,
    AsynchronousCalloutTask,
    AsynchronousCalloutTaskPollingParameters,
    AttachmentTask,
    AttachmentTaskParameters,
    BillingBillRunTask,
    BillingBillRunTaskParameters,
    BillingCurrencyConversionTask,
    BillingCurrencyConversionTaskParameters,
    BillingCustomDocumentTask,
    BillingCustomDocumentTaskParameters,
    BillingReverseInvoiceTask,
    BillingReverseInvoiceTaskParameters,
    BulkDataLoaderTask,
    BulkDataLoaderTaskParameters,
    CalloutTask,
    CalloutTaskParameters,
    CancelTask,
    CancelTaskParameters,
    CommonTaskParameters,
    CreateTask,
    CreateTaskParameters,
    CustomObjectCreateTask,
    CustomObjectCreateTaskParameters,
    CustomObjectDeleteTask,
    CustomObjectQueryTask,
    CustomObjectQueryTaskParameters,
    CustomObjectUpdateTask,
    CustomObjectUpdateTaskParameters,
    CustomPDFDocumentTask,
    CustomPdfDocumentTaskParameters,
    DataAQuATask,
    DataAquaTaskParameters,
    DataBillingPreviewRunTask,
    DataBillingPreviewRunTaskParameters,
    DataQueryTask,
    DataQueryTaskParameters,
    DataWarehouseTask,
    DataWarehouseTaskParameters,
    DelayTask,
    DelayTaskParameters,
    DeleteTask,
    DownloadS3Task,
    DownloadS3TaskParameters,
    DownloadSFTPTask,
    DownloadSftpTaskParameters,
    EmailTask,
    EmailTaskParameters,
    ExecuteWorkflowTask,
    ExecuteWorkflowTaskParameters,
    ExportTask,
    ExportTaskParameters,
    FileDownloadTask,
    FileDownloadTaskParameters,
    FileOperationsTask,
    FileOperationsTaskParameters,
    FileZuoraImportTask,
    FileZuoraImportTaskParameters,
    GraphQLQueryTask,
    GraphqlQueryTaskParameters,
    IfTask,
    IfTaskParameters,
    InvoiceGenerateTask,
    InvoiceGenerateTaskParameters,
    IterateTask,
    IterateTaskParameters,
    LogicCaseTask,
    LogicCaseTaskParameters,
    LogicCSVTranslatorTask,
    LogicCsvTranslatorTaskParameters,
    LogicJSONTransformTask,
    LogicJsonTransformTaskParameters,
    LogicLambdaTask,
    LogicLambdaTaskParameters,
    LogicLiquidTask,
    LogicLiquidTaskParameters,
    LogicMergeTask,
    LogicMergeTaskParameters,
    LogicResponseFormatterTask,
    LogicResponseFormatterTaskParameters,
    LogicXMLTransformTask,
    LogicXmlTransformTaskParameters,
    MediationSendEventsTask,
    MediationSendEventsTaskParameters,
    NewProductTask,
    NewProductTaskParameters,
    NotificationsKafkaTask,
    NotificationsKafkaTaskParameters,
    NotificationsSMSTask,
    NotificationsSmsTaskParameters,
    PaymentGatewayReconciliationTask,
    PaymentGatewayReconciliationTaskParameters,
    PaymentRunTask,
    PaymentRunTaskParameters,
    QueryTask,
    QueryTaskParameters,
    RemoveProductTask,
    RemoveProductTaskParameters,
    ReportingOracleFusionReportTask,
    ReportingOracleFusionReportTaskParameters,
    ReportingRunReportTask,
    ReportingRunReportTaskParameters,
    ResumeTask,
    ResumeTaskParameters,
    RevenueAllocateActionTask,
    RevenueAllocateActionTaskParameters,
    RevenueApplyImpairmentTask,
    RevenueApplyImpairmentTaskParameters,
    RevenueApplyVCTask,
    RevenueApplyVCTaskParameters,
    RevenueCloseRCTask,
    RevenueCloseRCTaskParameters,
    RevenueCreateManualRCTask,
    RevenueCreateManualRCTaskParameters,
    RevenueDeferCostTask,
    RevenueDeferCostTaskParameters,
    RevenueDeferRevenueTask,
    RevenueDeferRevenueTaskParameters,
    RevenueEditLineTask,
    RevenueEditLineTaskParameters,
    RevenueEditPOBAttributesTask,
    RevenueEditPOBAttributesTaskParameters,
    RevenueExpireVCTask,
    RevenueExpireVCTaskParameters,
    RevenueGenerateForecastTask,
    RevenueGenerateForecastTaskParameters,
    RevenueHoldTask,
    RevenueHoldTaskParameters,
    RevenueLinkDelinkTask,
    RevenueLinkDelinkTaskParameters,
    RevenueMovePOBTask,
    RevenueMovePOBTaskParameters,
    RevenueOpenRCTask,
    RevenueOpenRCTaskParameters,
    RevenueReleaseCostTask,
    RevenueReleaseCostTaskParameters,
    RevenueReleaseRevenueTask,
    RevenueReleaseRevenueTaskParameters,
    RevenueSwitchAllocationTask,
    RevenueSwitchAllocationTaskParameters,
    RevenueSwitchLeadLineTask,
    RevenueSwitchLeadLineTaskParameters,
    RevenueUnfreezeRCTask,
    RevenueUnfreezeRCTaskParameters,
    RevenueVoidBillingTask,
    RevenueVoidBillingTaskParameters,
    ScriptJavaScriptTask,
    ScriptJavascriptTaskParameters,
    SuspendTask,
    SuspendTaskParameters,
    UIPageTask,
    UiPageTaskParameters,
    UIStopTask,
    UiStopTaskParameters,
    UIWebShareTask,
    UiWebShareTaskParameters,
    UpdateTask,
    UpdateTaskParameters,
    UploadFTPTask,
    UploadFtpTaskParameters,
    UploadS3Task,
    UploadS3TaskParameters,
    UploadSFTPTask,
    UploadSftpTaskParameters,
    UsageImportTask,
    UsageImportTaskParameters,
    WriteOffTask,
    WriteOffTaskParameters,
)


class TaskTypeEnum(str, Enum):
    """Every supported Zuora Workflow ``action_type``."""

    APPROVAL = "Approval"
    ASYNCHRONOUSCALLOUT = "AsynchronousCallout"
    ATTACHMENT = "Attachment"
    BILLING_BILLRUN = "Billing::BillRun"
    BILLING_CURRENCYCONVERSION = "Billing::CurrencyConversion"
    BILLING_CUSTOMBILLINGDOCUMENT = "Billing::CustomBillingDocument"
    BILLING_REVERSEINVOICE = "Billing::ReverseInvoice"
    CALLOUT = "Callout"
    CANCEL = "Cancel"
    CREATE = "Create"
    CUSTOMOBJECT_CREATE = "CustomObject::Create"
    CUSTOMOBJECT_DELETE = "CustomObject::Delete"
    CUSTOMOBJECT_QUERY = "CustomObject::Query"
    CUSTOMOBJECT_UPDATE = "CustomObject::Update"
    DATA_AQUA = "Data::Aqua"
    DATA_BILLINGPREVIEWRUN = "Data::BillingPreviewRun"
    DATA_LINK = "Data::Link"
    DATA_WAREHOUSE = "Data::Warehouse"
    DELAY = "Delay"
    DELETE = "Delete"
    DOWNLOAD_S3 = "Download::S3"
    DOWNLOAD_SFTP = "Download::SFTP"
    EMAIL = "Email"
    EXECUTE_WORKFLOWTASK = "Execute::WorkflowTask"
    EXPORT = "Export"
    FILE_BULKDATALOADER = "File::BulkDataLoader"
    FILE_CUSTOMPDF_CUSTOMDOCUMENT = "File::CustomPDF::CustomDocument"
    FILE_DOWNLOADFILE = "File::DownloadFile"
    FILE_FILEOPERATIONS = "File::FileOperations"
    FILE_ZUORAIMPORT = "File::ZuoraImport"
    GRAPHQUERY = "GraphQuery"
    IF = "If"
    INVOICEGENERATE = "InvoiceGenerate"
    ITERATE = "Iterate"
    LOGIC_CSVTRANSLATOR = "Logic::CSVTranslator"
    LOGIC_CASE = "Logic::Case"
    LOGIC_JSONTRANSFORM = "Logic::JSONTransform"
    LOGIC_LAMBDA = "Logic::Lambda"
    LOGIC_LIQUID = "Logic::Liquid"
    LOGIC_MERGE = "Logic::Merge"
    LOGIC_RESPONSEFORMATTER = "Logic::ResponseFormatter"
    LOGIC_XMLTRANSFORM = "Logic::XMLTransform"
    MEDIATION_SENDEVENTS = "Mediation::SendEvents"
    NEWPRODUCT = "NewProduct"
    NOTIFICATIONS_KAFKA = "Notifications::Kafka"
    NOTIFICATIONS_SMS = "Notifications::SMS"
    PAYMENT_GATEWAYRECONCILIATION = "Payment::GatewayReconciliation"
    PAYMENT_PAYMENTRUN = "Payment::PaymentRun"
    QUERY = "Query"
    REMOVEPRODUCT = "RemoveProduct"
    REPORTING_ORACLEFUSIONREPORT = "Reporting::OracleFusionReport"
    REPORTING_RUNREPORT = "Reporting::RunReport"
    RESUME = "Resume"
    REVENUE_ALLOCATEACTION = "Revenue::AllocateAction"
    REVENUE_APPLYIMPAIRMENT = "Revenue::ApplyImpairment"
    REVENUE_APPLYVC = "Revenue::ApplyVc"
    REVENUE_CLOSERCTASK = "Revenue::CloseRcTask"
    REVENUE_CREATEMANUALRC = "Revenue::CreateManualRc"
    REVENUE_DEFERCOST = "Revenue::DeferCost"
    REVENUE_DEFERREVENUE = "Revenue::DeferRevenue"
    REVENUE_EDITLINE = "Revenue::EditLine"
    REVENUE_EDITPOBATTRIBUTES = "Revenue::EditPobAttributes"
    REVENUE_EXPIREVC = "Revenue::ExpireVc"
    REVENUE_GENERATEFORECAST = "Revenue::GenerateForecast"
    REVENUE_HOLD = "Revenue::Hold"
    REVENUE_LINKDELINK = "Revenue::LinkDelink"
    REVENUE_MOVEPOB = "Revenue::MovePob"
    REVENUE_OPENRCTASK = "Revenue::OpenRcTask"
    REVENUE_RELEASECOST = "Revenue::ReleaseCost"
    REVENUE_RELEASEREVENUE = "Revenue::ReleaseRevenue"
    REVENUE_SWITCHALLOCATION = "Revenue::SwitchAllocation"
    REVENUE_SWITCHLEADLINE = "Revenue::SwitchLeadLine"
    REVENUE_UNFREEZERC = "Revenue::UnfreezeRc"
    REVENUE_VOIDBILLING = "Revenue::VoidBilling"
    SCRIPT_JAVASCRIPT = "Script::JavaScript"
    SUSPEND = "Suspend"
    UI_PAGE = "UI::Page"
    UI_STOP = "UI::Stop"
    UI_WEBSHARE = "UI::WebShare"
    UPDATE = "Update"
    UPLOAD_FTP = "Upload::FTP"
    UPLOAD_S3 = "Upload::S3"
    UPLOAD_SFTP = "Upload::SFTP"
    USAGE_IMPORTUSAGE = "Usage::ImportUsage"
    WRITEOFF = "WriteOff"


TASK_TYPE_CONFIG_MAP: dict[str, type[BaseModel]] = {
    "Approval": ApprovalTaskParameters,
    "AsynchronousCallout": AsynchronousCalloutTaskPollingParameters,
    "Attachment": AttachmentTaskParameters,
    "Billing::BillRun": BillingBillRunTaskParameters,
    "Billing::CurrencyConversion": BillingCurrencyConversionTaskParameters,
    "Billing::CustomBillingDocument": BillingCustomDocumentTaskParameters,
    "Billing::ReverseInvoice": BillingReverseInvoiceTaskParameters,
    "Callout": CalloutTaskParameters,
    "Cancel": CancelTaskParameters,
    "Create": CreateTaskParameters,
    "CustomObject::Create": CustomObjectCreateTaskParameters,
    "CustomObject::Delete": CommonTaskParameters,
    "CustomObject::Query": CustomObjectQueryTaskParameters,
    "CustomObject::Update": CustomObjectUpdateTaskParameters,
    "Data::Aqua": DataAquaTaskParameters,
    "Data::BillingPreviewRun": DataBillingPreviewRunTaskParameters,
    "Data::Link": DataQueryTaskParameters,
    "Data::Warehouse": DataWarehouseTaskParameters,
    "Delay": DelayTaskParameters,
    "Delete": CommonTaskParameters,
    "Download::S3": DownloadS3TaskParameters,
    "Download::SFTP": DownloadSftpTaskParameters,
    "Email": EmailTaskParameters,
    "Execute::WorkflowTask": ExecuteWorkflowTaskParameters,
    "Export": ExportTaskParameters,
    "File::BulkDataLoader": BulkDataLoaderTaskParameters,
    "File::CustomPDF::CustomDocument": CustomPdfDocumentTaskParameters,
    "File::DownloadFile": FileDownloadTaskParameters,
    "File::FileOperations": FileOperationsTaskParameters,
    "File::ZuoraImport": FileZuoraImportTaskParameters,
    "GraphQuery": GraphqlQueryTaskParameters,
    "If": IfTaskParameters,
    "InvoiceGenerate": InvoiceGenerateTaskParameters,
    "Iterate": IterateTaskParameters,
    "Logic::CSVTranslator": LogicCsvTranslatorTaskParameters,
    "Logic::Case": LogicCaseTaskParameters,
    "Logic::JSONTransform": LogicJsonTransformTaskParameters,
    "Logic::Lambda": LogicLambdaTaskParameters,
    "Logic::Liquid": LogicLiquidTaskParameters,
    "Logic::Merge": LogicMergeTaskParameters,
    "Logic::ResponseFormatter": LogicResponseFormatterTaskParameters,
    "Logic::XMLTransform": LogicXmlTransformTaskParameters,
    "Mediation::SendEvents": MediationSendEventsTaskParameters,
    "NewProduct": NewProductTaskParameters,
    "Notifications::Kafka": NotificationsKafkaTaskParameters,
    "Notifications::SMS": NotificationsSmsTaskParameters,
    "Payment::GatewayReconciliation": PaymentGatewayReconciliationTaskParameters,
    "Payment::PaymentRun": PaymentRunTaskParameters,
    "Query": QueryTaskParameters,
    "RemoveProduct": RemoveProductTaskParameters,
    "Reporting::OracleFusionReport": ReportingOracleFusionReportTaskParameters,
    "Reporting::RunReport": ReportingRunReportTaskParameters,
    "Resume": ResumeTaskParameters,
    "Revenue::AllocateAction": RevenueAllocateActionTaskParameters,
    "Revenue::ApplyImpairment": RevenueApplyImpairmentTaskParameters,
    "Revenue::ApplyVc": RevenueApplyVCTaskParameters,
    "Revenue::CloseRcTask": RevenueCloseRCTaskParameters,
    "Revenue::CreateManualRc": RevenueCreateManualRCTaskParameters,
    "Revenue::DeferCost": RevenueDeferCostTaskParameters,
    "Revenue::DeferRevenue": RevenueDeferRevenueTaskParameters,
    "Revenue::EditLine": RevenueEditLineTaskParameters,
    "Revenue::EditPobAttributes": RevenueEditPOBAttributesTaskParameters,
    "Revenue::ExpireVc": RevenueExpireVCTaskParameters,
    "Revenue::GenerateForecast": RevenueGenerateForecastTaskParameters,
    "Revenue::Hold": RevenueHoldTaskParameters,
    "Revenue::LinkDelink": RevenueLinkDelinkTaskParameters,
    "Revenue::MovePob": RevenueMovePOBTaskParameters,
    "Revenue::OpenRcTask": RevenueOpenRCTaskParameters,
    "Revenue::ReleaseCost": RevenueReleaseCostTaskParameters,
    "Revenue::ReleaseRevenue": RevenueReleaseRevenueTaskParameters,
    "Revenue::SwitchAllocation": RevenueSwitchAllocationTaskParameters,
    "Revenue::SwitchLeadLine": RevenueSwitchLeadLineTaskParameters,
    "Revenue::UnfreezeRc": RevenueUnfreezeRCTaskParameters,
    "Revenue::VoidBilling": RevenueVoidBillingTaskParameters,
    "Script::JavaScript": ScriptJavascriptTaskParameters,
    "Suspend": SuspendTaskParameters,
    "UI::Page": UiPageTaskParameters,
    "UI::Stop": UiStopTaskParameters,
    "UI::WebShare": UiWebShareTaskParameters,
    "Update": UpdateTaskParameters,
    "Upload::FTP": UploadFtpTaskParameters,
    "Upload::S3": UploadS3TaskParameters,
    "Upload::SFTP": UploadSftpTaskParameters,
    "Usage::ImportUsage": UsageImportTaskParameters,
    "WriteOff": WriteOffTaskParameters,
}


TASK_TYPE_TASK_MAP: dict[str, type[BaseModel]] = {
    "Approval": ApprovalTask,
    "AsynchronousCallout": AsynchronousCalloutTask,
    "Attachment": AttachmentTask,
    "Billing::BillRun": BillingBillRunTask,
    "Billing::CurrencyConversion": BillingCurrencyConversionTask,
    "Billing::CustomBillingDocument": BillingCustomDocumentTask,
    "Billing::ReverseInvoice": BillingReverseInvoiceTask,
    "Callout": CalloutTask,
    "Cancel": CancelTask,
    "Create": CreateTask,
    "CustomObject::Create": CustomObjectCreateTask,
    "CustomObject::Delete": CustomObjectDeleteTask,
    "CustomObject::Query": CustomObjectQueryTask,
    "CustomObject::Update": CustomObjectUpdateTask,
    "Data::Aqua": DataAQuATask,
    "Data::BillingPreviewRun": DataBillingPreviewRunTask,
    "Data::Link": DataQueryTask,
    "Data::Warehouse": DataWarehouseTask,
    "Delay": DelayTask,
    "Delete": DeleteTask,
    "Download::S3": DownloadS3Task,
    "Download::SFTP": DownloadSFTPTask,
    "Email": EmailTask,
    "Execute::WorkflowTask": ExecuteWorkflowTask,
    "Export": ExportTask,
    "File::BulkDataLoader": BulkDataLoaderTask,
    "File::CustomPDF::CustomDocument": CustomPDFDocumentTask,
    "File::DownloadFile": FileDownloadTask,
    "File::FileOperations": FileOperationsTask,
    "File::ZuoraImport": FileZuoraImportTask,
    "GraphQuery": GraphQLQueryTask,
    "If": IfTask,
    "InvoiceGenerate": InvoiceGenerateTask,
    "Iterate": IterateTask,
    "Logic::CSVTranslator": LogicCSVTranslatorTask,
    "Logic::Case": LogicCaseTask,
    "Logic::JSONTransform": LogicJSONTransformTask,
    "Logic::Lambda": LogicLambdaTask,
    "Logic::Liquid": LogicLiquidTask,
    "Logic::Merge": LogicMergeTask,
    "Logic::ResponseFormatter": LogicResponseFormatterTask,
    "Logic::XMLTransform": LogicXMLTransformTask,
    "Mediation::SendEvents": MediationSendEventsTask,
    "NewProduct": NewProductTask,
    "Notifications::Kafka": NotificationsKafkaTask,
    "Notifications::SMS": NotificationsSMSTask,
    "Payment::GatewayReconciliation": PaymentGatewayReconciliationTask,
    "Payment::PaymentRun": PaymentRunTask,
    "Query": QueryTask,
    "RemoveProduct": RemoveProductTask,
    "Reporting::OracleFusionReport": ReportingOracleFusionReportTask,
    "Reporting::RunReport": ReportingRunReportTask,
    "Resume": ResumeTask,
    "Revenue::AllocateAction": RevenueAllocateActionTask,
    "Revenue::ApplyImpairment": RevenueApplyImpairmentTask,
    "Revenue::ApplyVc": RevenueApplyVCTask,
    "Revenue::CloseRcTask": RevenueCloseRCTask,
    "Revenue::CreateManualRc": RevenueCreateManualRCTask,
    "Revenue::DeferCost": RevenueDeferCostTask,
    "Revenue::DeferRevenue": RevenueDeferRevenueTask,
    "Revenue::EditLine": RevenueEditLineTask,
    "Revenue::EditPobAttributes": RevenueEditPOBAttributesTask,
    "Revenue::ExpireVc": RevenueExpireVCTask,
    "Revenue::GenerateForecast": RevenueGenerateForecastTask,
    "Revenue::Hold": RevenueHoldTask,
    "Revenue::LinkDelink": RevenueLinkDelinkTask,
    "Revenue::MovePob": RevenueMovePOBTask,
    "Revenue::OpenRcTask": RevenueOpenRCTask,
    "Revenue::ReleaseCost": RevenueReleaseCostTask,
    "Revenue::ReleaseRevenue": RevenueReleaseRevenueTask,
    "Revenue::SwitchAllocation": RevenueSwitchAllocationTask,
    "Revenue::SwitchLeadLine": RevenueSwitchLeadLineTask,
    "Revenue::UnfreezeRc": RevenueUnfreezeRCTask,
    "Revenue::VoidBilling": RevenueVoidBillingTask,
    "Script::JavaScript": ScriptJavaScriptTask,
    "Suspend": SuspendTask,
    "UI::Page": UIPageTask,
    "UI::Stop": UIStopTask,
    "UI::WebShare": UIWebShareTask,
    "Update": UpdateTask,
    "Upload::FTP": UploadFTPTask,
    "Upload::S3": UploadS3Task,
    "Upload::SFTP": UploadSFTPTask,
    "Usage::ImportUsage": UsageImportTask,
    "WriteOff": WriteOffTask,
}


TaskUnion = Annotated[
    Union[
        ApprovalTask,
        AsynchronousCalloutTask,
        AttachmentTask,
        BillingBillRunTask,
        BillingCurrencyConversionTask,
        BillingCustomDocumentTask,
        BillingReverseInvoiceTask,
        CalloutTask,
        CancelTask,
        CreateTask,
        CustomObjectCreateTask,
        CustomObjectDeleteTask,
        CustomObjectQueryTask,
        CustomObjectUpdateTask,
        DataAQuATask,
        DataBillingPreviewRunTask,
        DataQueryTask,
        DataWarehouseTask,
        DelayTask,
        DeleteTask,
        DownloadS3Task,
        DownloadSFTPTask,
        EmailTask,
        ExecuteWorkflowTask,
        ExportTask,
        BulkDataLoaderTask,
        CustomPDFDocumentTask,
        FileDownloadTask,
        FileOperationsTask,
        FileZuoraImportTask,
        GraphQLQueryTask,
        IfTask,
        InvoiceGenerateTask,
        IterateTask,
        LogicCSVTranslatorTask,
        LogicCaseTask,
        LogicJSONTransformTask,
        LogicLambdaTask,
        LogicLiquidTask,
        LogicMergeTask,
        LogicResponseFormatterTask,
        LogicXMLTransformTask,
        MediationSendEventsTask,
        NewProductTask,
        NotificationsKafkaTask,
        NotificationsSMSTask,
        PaymentGatewayReconciliationTask,
        PaymentRunTask,
        QueryTask,
        RemoveProductTask,
        ReportingOracleFusionReportTask,
        ReportingRunReportTask,
        ResumeTask,
        RevenueAllocateActionTask,
        RevenueApplyImpairmentTask,
        RevenueApplyVCTask,
        RevenueCloseRCTask,
        RevenueCreateManualRCTask,
        RevenueDeferCostTask,
        RevenueDeferRevenueTask,
        RevenueEditLineTask,
        RevenueEditPOBAttributesTask,
        RevenueExpireVCTask,
        RevenueGenerateForecastTask,
        RevenueHoldTask,
        RevenueLinkDelinkTask,
        RevenueMovePOBTask,
        RevenueOpenRCTask,
        RevenueReleaseCostTask,
        RevenueReleaseRevenueTask,
        RevenueSwitchAllocationTask,
        RevenueSwitchLeadLineTask,
        RevenueUnfreezeRCTask,
        RevenueVoidBillingTask,
        ScriptJavaScriptTask,
        SuspendTask,
        UIPageTask,
        UIStopTask,
        UIWebShareTask,
        UpdateTask,
        UploadFTPTask,
        UploadS3Task,
        UploadSFTPTask,
        UsageImportTask,
        WriteOffTask,
    ],
    Field(discriminator="action_type"),
]


TASK_LINKAGE_TYPES: dict[str, tuple[str, ...] | None] = {
    "Approval": ("Approve", "Reject", "Timeout", "Failure"),
    "AsynchronousCallout": ("Success", "Failure"),
    "Attachment": ("Success", "Failure"),
    "Billing::BillRun": ("Success", "Failure"),
    "Billing::CurrencyConversion": ("Success", "Failure"),
    "Billing::CustomBillingDocument": ("Success", "Failure"),
    "Billing::ReverseInvoice": ("Success", "Failure"),
    "Callout": ("Success", "Failure"),
    "Cancel": ("Success", "Failure"),
    "Create": ("Success", "Failure"),
    "CustomObject::Create": ("Success", "Failure"),
    "CustomObject::Delete": ("Success", "Failure"),
    "CustomObject::Query": ("Success", "Failure"),
    "CustomObject::Update": ("Success", "Failure"),
    "Data::Aqua": ("Success", "Failure"),
    "Data::BillingPreviewRun": ("Success", "Failure"),
    "Data::Link": ("Success", "Failure"),
    "Data::Warehouse": ("Success", "Failure"),
    "Delay": ("Success", "Failure"),
    "Delete": ("Success", "Failure"),
    "Download::S3": ("Success", "Failure"),
    "Download::SFTP": ("Success", "Failure"),
    "Email": ("Success", "Failure"),
    "Execute::WorkflowTask": ("Success", "Failure"),
    "Export": ("Success", "Failure"),
    "File::BulkDataLoader": ("Success", "Failure"),
    "File::CustomPDF::CustomDocument": ("Success", "Failure"),
    "File::DownloadFile": ("Success", "Failure"),
    "File::FileOperations": ("Success", "Failure"),
    "File::ZuoraImport": ("Success", "Failure"),
    "GraphQuery": ("Success", "Failure"),
    "If": ("True", "False", "Failure"),
    "InvoiceGenerate": ("Success", "Failure"),
    "Iterate": ("For Each", "Complete", "Failure"),
    "Logic::CSVTranslator": ("Success", "Failure"),
    "Logic::Case": None,  # dynamic (Case_1..Case_N + Case_Else)
    "Logic::JSONTransform": ("Success", "Failure"),
    "Logic::Lambda": ("Success", "Failure"),
    "Logic::Liquid": ("Success", "Failure"),
    "Logic::Merge": ("Success", "Failure"),
    "Logic::ResponseFormatter": ("Success", "Failure"),
    "Logic::XMLTransform": ("Success", "Failure"),
    "Mediation::SendEvents": ("Success", "Failure"),
    "NewProduct": ("Success", "Failure"),
    "Notifications::Kafka": ("Success", "Failure"),
    "Notifications::SMS": ("Success", "Failure"),
    "Payment::GatewayReconciliation": ("Success", "Failure"),
    "Payment::PaymentRun": ("Success", "Failure"),
    "Query": ("Success", "Failure"),
    "RemoveProduct": ("Success", "Failure"),
    "Reporting::OracleFusionReport": ("Success", "Failure"),
    "Reporting::RunReport": ("Success", "Failure"),
    "Resume": ("Success", "Failure"),
    "Revenue::AllocateAction": ("Success", "Failure"),
    "Revenue::ApplyImpairment": ("Success", "Failure"),
    "Revenue::ApplyVc": ("Success", "Failure"),
    "Revenue::CloseRcTask": ("Success", "Failure"),
    "Revenue::CreateManualRc": ("Success", "Failure"),
    "Revenue::DeferCost": ("Success", "Failure"),
    "Revenue::DeferRevenue": ("Success", "Failure"),
    "Revenue::EditLine": ("Success", "Failure"),
    "Revenue::EditPobAttributes": ("Success", "Failure"),
    "Revenue::ExpireVc": ("Success", "Failure"),
    "Revenue::GenerateForecast": ("Success", "Failure"),
    "Revenue::Hold": ("Success", "Failure"),
    "Revenue::LinkDelink": ("Success", "Failure"),
    "Revenue::MovePob": ("Success", "Failure"),
    "Revenue::OpenRcTask": ("Success", "Failure"),
    "Revenue::ReleaseCost": ("Success", "Failure"),
    "Revenue::ReleaseRevenue": ("Success", "Failure"),
    "Revenue::SwitchAllocation": ("Success", "Failure"),
    "Revenue::SwitchLeadLine": ("Success", "Failure"),
    "Revenue::UnfreezeRc": ("Success", "Failure"),
    "Revenue::VoidBilling": ("Success", "Failure"),
    "Script::JavaScript": ("Success", "Failure"),
    "Suspend": ("Success", "Failure"),
    "UI::Page": ("Success", "Failure"),
    "UI::Stop": ("Success", "Failure"),
    "UI::WebShare": ("Success", "Timeout", "Failure"),
    "Update": ("Success", "Failure"),
    "Upload::FTP": ("Success", "Failure"),
    "Upload::S3": ("Success", "Failure"),
    "Upload::SFTP": ("Success", "Failure"),
    "Usage::ImportUsage": ("Success", "Failure"),
    "WriteOff": ("Success", "Failure"),
}


def get_linkage_types(action_type: str) -> tuple[str, ...] | None:
    """Return valid outgoing linkage labels for a task, or ``None`` if dynamic.

    Unknown action types return an empty tuple.
    """
    if action_type not in TASK_LINKAGE_TYPES:
        return ()
    return TASK_LINKAGE_TYPES[action_type]
