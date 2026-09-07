# Zuora object relationships and foreign keys

Per-object: **References** (this object's FKs / to-one navigation / to-many children) and **Referenced by** (other objects whose FK column points at this one).

References use ``FieldName -> TargetType (cardinality[, as Alias])`` when the FK column lives on this object; aliases without an FK column (indirect joins, to-many) appear as ``Alias (cardinality[, type ...][, via Path])``.

## Account

**References (foreign keys / relations):**
- DefaultPaymentMethodId -> PaymentMethod (to-one, as DefaultPaymentMethod)
- AccountTemplate (to-one, via Account.AccountTemplate)
- BillToContact (to-one, type Contact, via Account.BillToContact)
- EInvoiceProfile (to-one, via Account.EInvoiceProfile)
- ParentAccount (to-one, type Account, via Account.ParentAccount)
- ShipToContact (to-one, type Contact, via Account.ShipToContact)
- SoldToContact (to-one, type Contact, via Account.SoldToContact)
- PaymentMethodPriority (to-many, via Account.PaymentMethodPriority)

**Referenced by:**
- BillingPreviewRunResult.AccountId
- CreditBalanceAdjustment.AccountId
- DeliveryAdjustment.AccountId
- Fund.AccountId
- Invoice.AccountId
- InvoiceAdjustment.AccountId
- InvoiceItemAdjustment.AccountId
- JournalEntryDetailFXGainLoss.AccountId
- Payment.AccountId
- PrepaidBalance.AccountId
- PrepaidBalanceTransaction.AccountId
- ProcessedUsage.AccountId
- RatePlan.InvoiceOwnerId
- RatePlanCharge.InvoiceOwnerId
- RatingResult.AccountId
- Refund.AccountId
- Subscription.AccountId
- Subscription.InvoiceOwnerId
- Usage.AccountId
- ValidityPeriodSummary.AccountId

## AccountingCode

**References:** none

**Referenced by:** none

## AccountingPeriod

**References:** none

**Referenced by:** none

## AchNocEventLog

**References:** none

**Referenced by:** none

## Amendment

**References:** none

**Referenced by:**
- RatePlan.AmendmentId

## ApplicationGroup

**References (foreign keys / relations):**
- Payment (to-one, via ApplicationGroup.Payment)
- PaymentMethod (to-one, via ApplicationGroup.Payment.PaymentMethod)
- PaymentMethodSnapshot (to-one, via ApplicationGroup.Payment.PaymentMethodSnapshot)
- Refund (to-one, via ApplicationGroup.Refund)

**Referenced by:** none

## BillingPreviewRun

**References:** none

**Referenced by:** none

## BillingPreviewRunResult

**References (foreign keys / relations):**
- AccountId -> Account (to-one)
- RatePlanChargeId -> RatePlanCharge (to-one)
- SubscriptionId -> Subscription (to-one)
- Amendment (to-one, via BillingPreviewRunResult.RatePlanCharge.RatePlan.Amendment)
- BillToContact (to-one, type Contact, via BillingPreviewRunResult.Account.BillToContact)
- DefaultPaymentMethod (to-one, type PaymentMethod, via BillingPreviewRunResult.Account.DefaultPaymentMethod)
- DeferredRevenueAccountingCode (to-one, type AccountingCode, via BillingPreviewRunResult.RatePlanCharge.DeferredRevenueAccountingCode)
- ParentAccount (to-one, type Account, via BillingPreviewRunResult.Account.ParentAccount)
- Product (to-one, via BillingPreviewRunResult.RatePlanCharge.RatePlan.ProductRatePlan.Product)
- ProductRatePlan (to-one, via BillingPreviewRunResult.RatePlanCharge.RatePlan.ProductRatePlan)
- ProductRatePlanCharge (to-one, via BillingPreviewRunResult.RatePlanCharge.ProductRatePlanCharge)
- RatePlan (to-one, via BillingPreviewRunResult.RatePlanCharge.RatePlan)
- RecognizedRevenueAccountingCode (to-one, type AccountingCode, via BillingPreviewRunResult.RatePlanCharge.RecognizedRevenueAccountingCode)
- ShipToContact (to-one, type Contact, via BillingPreviewRunResult.Account.ShipToContact)
- SoldToContact (to-one, type Contact, via BillingPreviewRunResult.Account.SoldToContact)

**Referenced by:** none

## BillingRun

**References:** none

**Referenced by:** none

## BillingTransaction

**References (foreign keys / relations):**
- Amendment (to-one, via BillingTransaction.SubscriptionRatePlan.Amendment)
- BillToContact (to-one, type Contact, via BillingTransaction.SubscriptionOwner.BillToContact)
- DefaultPaymentMethod (to-one, type PaymentMethod, via BillingTransaction.SubscriptionOwner.DefaultPaymentMethod)
- DiscountAppliedToRatePlanCharge (to-one, type RatePlanCharge, via BillingTransaction.DiscountAppliedToRatePlanCharge)
- ParentAccount (to-one, type Account, via BillingTransaction.SubscriptionOwner.ParentAccount)
- Product (to-one, via BillingTransaction.ProductRatePlan.Product)
- ProductRatePlan (to-one, via BillingTransaction.ProductRatePlan)
- ProductRatePlanCharge (to-one, via BillingTransaction.ProductRatePlanCharge)
- RatePlan (to-one, via BillingTransaction.RatePlanCharge.RatePlan)
- RatePlanCharge (to-one, via BillingTransaction.RatePlanCharge)
- ShipToContact (to-one, type Contact, via BillingTransaction.SubscriptionOwner.ShipToContact)
- SoldToContact (to-one, type Contact, via BillingTransaction.SubscriptionOwner.SoldToContact)
- Subscription (to-one, via BillingTransaction.Subscription)
- SubscriptionOwner (to-one, type Account, via BillingTransaction.SubscriptionOwner)
- SubscriptionRatePlan (to-one, type RatePlan, via BillingTransaction.SubscriptionRatePlan)

**Referenced by:** none

## BookingTransaction

**References (foreign keys / relations):**
- Amendment (to-one, via BookingTransaction.SubscriptionRatePlan.Amendment)
- BillToContact (to-one, type Contact, via BookingTransaction.SubscriptionOwner.BillToContact)
- DefaultPaymentMethod (to-one, type PaymentMethod, via BookingTransaction.SubscriptionOwner.DefaultPaymentMethod)
- DiscountAppliedToRatePlanCharge (to-one, type RatePlanCharge, via BookingTransaction.DiscountAppliedToRatePlanCharge)
- DiscountAppliedToSubscriptionRatePlan (to-one, type RatePlan, via BookingTransaction.DiscountAppliedToSubscriptionRatePlan)
- InvoiceOwner (to-one, type Account, via BookingTransaction.InvoiceOwner)
- Order (to-one, via BookingTransaction.Order)
- OrderLineItem (to-one, via BookingTransaction.OrderLineItem)
- ParentAccount (to-one, type Account, via BookingTransaction.SubscriptionOwner.ParentAccount)
- Product (to-one, via BookingTransaction.Product)
- ProductRatePlan (to-one, via BookingTransaction.ProductRatePlan)
- ProductRatePlanCharge (to-one, via BookingTransaction.ProductRatePlanCharge)
- RatePlan (to-one, via BookingTransaction.RatePlanCharge.RatePlan)
- RatePlanCharge (to-one, via BookingTransaction.RatePlanCharge)
- ShipToContact (to-one, type Contact, via BookingTransaction.SubscriptionOwner.ShipToContact)
- SoldToContact (to-one, type Contact, via BookingTransaction.SubscriptionOwner.SoldToContact)
- Subscription (to-one, via BookingTransaction.Subscription)
- SubscriptionOwner (to-one, type Account, via BookingTransaction.SubscriptionOwner)
- SubscriptionRatePlan (to-one, type RatePlan, via BookingTransaction.SubscriptionRatePlan)

**Referenced by:** none

## CalloutHistory

**References (foreign keys / relations):**
- Account (to-one, via CalloutHistory.Account)
- BillToContact (to-one, type Contact, via CalloutHistory.Account.BillToContact)
- DefaultPaymentMethod (to-one, type PaymentMethod, via CalloutHistory.Account.DefaultPaymentMethod)
- ParentAccount (to-one, type Account, via CalloutHistory.Account.ParentAccount)
- ShipToContact (to-one, type Contact, via CalloutHistory.Account.ShipToContact)
- SoldToContact (to-one, type Contact, via CalloutHistory.Account.SoldToContact)

**Referenced by:** none

## CommunicationProfile

**References:** none

**Referenced by:** none

## Contact

**References:** none

**Referenced by:**
- Invoice.BillToContactId
- Invoice.SoldToContactId
- Subscription.SubscriptionBillToId
- Subscription.SubscriptionShipToId
- Subscription.SubscriptionSoldToId

## ContactSnapshot

**References:** none

**Referenced by:**
- Invoice.BillToContactSnapshotId
- Invoice.SoldToContactSnapshotId
- Subscription.SubscriptionBillToSnapshotId
- Subscription.SubscriptionShipToSnapshotId
- Subscription.SubscriptionSoldToSnapshotId

## CreditBalanceAdjustment

**References (foreign keys / relations):**
- AccountId -> Account (to-one)
- AccountingPeriod (to-one, via CreditBalanceAdjustment.JournalEntry.AccountingPeriod)
- AccountReceivableAccountingCode (to-one, type AccountingCode, via CreditBalanceAdjustment.AccountReceivableAccountingCode)
- BillToContact (to-one, type Contact, via CreditBalanceAdjustment.Account.BillToContact)
- CashAccountingCode (to-one, type AccountingCode, via CreditBalanceAdjustment.CashAccountingCode)
- CustomerCashOnAccountAccountingCode (to-one, type AccountingCode, via CreditBalanceAdjustment.CustomerCashOnAccountAccountingCode)
- DefaultPaymentMethod (to-one, type PaymentMethod, via CreditBalanceAdjustment.Account.DefaultPaymentMethod)
- Invoice (to-one, via CreditBalanceAdjustment.Invoice)
- JournalEntry (to-one, via CreditBalanceAdjustment.JournalEntry)
- JournalRun (to-one, via CreditBalanceAdjustment.JournalEntry.JournalRun)
- ParentAccount (to-one, type Account, via CreditBalanceAdjustment.Account.ParentAccount)
- Payment (to-one, via CreditBalanceAdjustment.Payment)
- PaymentMethod (to-one, via CreditBalanceAdjustment.Payment.PaymentMethod)
- PaymentMethodSnapshot (to-one, via CreditBalanceAdjustment.Refund.PaymentMethodSnapshot)
- Refund (to-one, via CreditBalanceAdjustment.Refund)
- ShipToContact (to-one, type Contact, via CreditBalanceAdjustment.Account.ShipToContact)
- SoldToContact (to-one, type Contact, via CreditBalanceAdjustment.Account.SoldToContact)

**Referenced by:** none

## CreditMemo

**References (foreign keys / relations):**
- Account (to-one, via CreditMemo.Account)
- BillingDocumentPDFGeneration (to-one, via CreditMemo.BillingDocumentPDFGeneration)
- BillToContact (to-one, type Contact, via CreditMemo.Account.BillToContact)
- BillToContactSnapshot (to-one, type ContactSnapshot, via CreditMemo.BillToContactSnapshot)
- CreditMemoBillToContact (to-one, type Contact, via CreditMemo.CreditMemoBillToContact)
- DebitMemo (to-one, via CreditMemo.DebitMemo)
- DefaultPaymentMethod (to-one, type PaymentMethod, via CreditMemo.Account.DefaultPaymentMethod)
- EInvoiceProfile (to-one, via CreditMemo.Account.EInvoiceProfile)
- Invoice (to-one, via CreditMemo.Invoice)
- ParentAccount (to-one, type Account, via CreditMemo.Account.ParentAccount)
- ShipToContact (to-one, type Contact, via CreditMemo.Account.ShipToContact)
- ShipToContactSnapshot (to-one, type ContactSnapshot, via CreditMemo.ShipToContactSnapshot)
- SoldToContact (to-one, type Contact, via CreditMemo.Account.SoldToContact)
- SoldToContactSnapshot (to-one, type ContactSnapshot, via CreditMemo.SoldToContactSnapshot)

**Referenced by:** none

## CreditMemoApplication

**References (foreign keys / relations):**
- Account (to-one, via CreditMemoApplication.CreditMemo.Account)
- ApplicationGroup (to-one, via CreditMemoApplication.ApplicationGroup)
- BillToContact (to-one, type Contact, via CreditMemoApplication.CreditMemo.Account.BillToContact)
- CreditMemo (to-one, via CreditMemoApplication.CreditMemo)
- DebitMemo (to-one, via CreditMemoApplication.DebitMemo)
- DefaultPaymentMethod (to-one, type PaymentMethod, via CreditMemoApplication.CreditMemo.Account.DefaultPaymentMethod)
- Invoice (to-one, via CreditMemoApplication.Invoice)
- ParentAccount (to-one, type Account, via CreditMemoApplication.CreditMemo.Account.ParentAccount)
- ShipToContact (to-one, type Contact, via CreditMemoApplication.CreditMemo.Account.ShipToContact)
- SoldToContact (to-one, type Contact, via CreditMemoApplication.CreditMemo.Account.SoldToContact)

**Referenced by:** none

## CreditMemoApplicationItem

**References (foreign keys / relations):**
- Account (to-one, via CreditMemoApplicationItem.CreditMemoApplication.CreditMemo.Account)
- AccountingPeriod (to-one, via CreditMemoApplicationItem.JournalEntry.AccountingPeriod)
- ApplicationGroup (to-one, via CreditMemoApplicationItem.ApplicationGroup)
- BillToContact (to-one, type Contact, via CreditMemoApplicationItem.CreditMemoApplication.CreditMemo.Account.BillToContact)
- CreditMemo (to-one, via CreditMemoApplicationItem.CreditMemoApplication.CreditMemo)
- CreditMemoApplication (to-one, via CreditMemoApplicationItem.CreditMemoApplication)
- CreditMemoItem (to-one, via CreditMemoApplicationItem.CreditMemoItem)
- CreditTaxationItem (to-one, via CreditMemoApplicationItem.CreditTaxationItem)
- DebitMemo (to-one, via CreditMemoApplicationItem.CreditMemoApplication.DebitMemo)
- DebitMemoItem (to-one, via CreditMemoApplicationItem.DebitMemoItem)
- DebitTaxationItem (to-one, via CreditMemoApplicationItem.DebitTaxationItem)
- DefaultPaymentMethod (to-one, type PaymentMethod, via CreditMemoApplicationItem.CreditMemoApplication.CreditMemo.Account.DefaultPaymentMethod)
- Invoice (to-one, via CreditMemoApplicationItem.InvoiceItem.Invoice)
- InvoiceItem (to-one, via CreditMemoApplicationItem.InvoiceItem)
- JournalEntry (to-one, via CreditMemoApplicationItem.JournalEntry)
- JournalRun (to-one, via CreditMemoApplicationItem.JournalEntry.JournalRun)
- ParentAccount (to-one, type Account, via CreditMemoApplicationItem.CreditMemoApplication.CreditMemo.Account.ParentAccount)
- ShipToContact (to-one, type Contact, via CreditMemoApplicationItem.CreditMemoApplication.CreditMemo.Account.ShipToContact)
- SoldToContact (to-one, type Contact, via CreditMemoApplicationItem.CreditMemoApplication.CreditMemo.Account.SoldToContact)
- TaxationItem (to-one, via CreditMemoApplicationItem.TaxationItem)

**Referenced by:** none

## CreditMemoItem

**References (foreign keys / relations):**
- Account (to-one, via CreditMemoItem.CreditMemo.Account)
- AccountingPeriod (to-one, via CreditMemoItem.JournalEntry.AccountingPeriod)
- AccountReceivableAccountingCode (to-one, type AccountingCode, via CreditMemoItem.AccountReceivableAccountingCode)
- Amendment (to-one, via CreditMemoItem.RatePlanCharge.RatePlan.Amendment)
- BillToContact (to-one, type Contact, via CreditMemoItem.CreditMemo.Account.BillToContact)
- BillToContactSnapshot (to-one, type ContactSnapshot, via CreditMemoItem.CreditMemo.BillToContactSnapshot)
- CreditMemo (to-one, via CreditMemoItem.CreditMemo)
- CreditMemoBillToContact (to-one, type Contact, via CreditMemoItem.CreditMemo.CreditMemoBillToContact)
- CreditMemoItemShipToContact (to-one, type Contact, via CreditMemoItem.CreditMemoItemShipToContact)
- CreditMemoItemSoldToContact (to-one, type Contact, via CreditMemoItem.CreditMemoItemSoldToContact)
- CreditMemoItemSoldToContactSnapshot (to-one, type ContactSnapshot, via CreditMemoItem.CreditMemoItemSoldToContactSnapshot)
- DebitMemo (to-one, via CreditMemoItem.CreditMemo.DebitMemo)
- DebitMemoItem (to-one, via CreditMemoItem.DebitMemoItem)
- DefaultPaymentMethod (to-one, type PaymentMethod, via CreditMemoItem.CreditMemo.Account.DefaultPaymentMethod)
- DeferredRevenueAccountingCode (to-one, type AccountingCode, via CreditMemoItem.DeferredRevenueAccountingCode)
- Fulfillment (to-one, via CreditMemoItem.Fulfillment)
- Invoice (to-one, via CreditMemoItem.InvoiceItem.Invoice)
- InvoiceItem (to-one, via CreditMemoItem.InvoiceItem)
- JournalEntry (to-one, via CreditMemoItem.JournalEntry)
- JournalRun (to-one, via CreditMemoItem.JournalEntry.JournalRun)
- NonRevenueWriteOffAccountingCode (to-one, type AccountingCode, via CreditMemoItem.NonRevenueWriteOffAccountingCode)
- OnAccountAccountingCode (to-one, type AccountingCode, via CreditMemoItem.OnAccountAccountingCode)
- OrderLineItem (to-one, via CreditMemoItem.OrderLineItem)
- ParentAccount (to-one, type Account, via CreditMemoItem.CreditMemo.Account.ParentAccount)
- Product (to-one, via CreditMemoItem.ProductRatePlanCharge.ProductRatePlan.Product)
- ProductRatePlan (to-one, via CreditMemoItem.ProductRatePlanCharge.ProductRatePlan)
- ProductRatePlanCharge (to-one, via CreditMemoItem.ProductRatePlanCharge)
- RatePlan (to-one, via CreditMemoItem.RatePlanCharge.RatePlan)
- RatePlanCharge (to-one, via CreditMemoItem.RatePlanCharge)
- RecognizedRevenueAccountingCode (to-one, type AccountingCode, via CreditMemoItem.RecognizedRevenueAccountingCode)
- ShipToContact (to-one, type Contact, via CreditMemoItem.CreditMemo.Account.ShipToContact)
- ShipToContactSnapshot (to-one, type ContactSnapshot, via CreditMemoItem.CreditMemo.ShipToContactSnapshot)
- SoldToContact (to-one, type Contact, via CreditMemoItem.CreditMemo.Account.SoldToContact)
- SoldToContactSnapshot (to-one, type ContactSnapshot, via CreditMemoItem.CreditMemo.SoldToContactSnapshot)
- Subscription (to-one, via CreditMemoItem.Subscription)

**Referenced by:** none

## CreditMemoPart

**References (foreign keys / relations):**
- Account (to-one, via CreditMemoPart.Account)
- BillToContact (to-one, type Contact, via CreditMemoPart.Account.BillToContact)
- CreditMemo (to-one, via CreditMemoPart.CreditMemo)
- DebitMemo (to-one, via CreditMemoPart.DebitMemo)
- DefaultPaymentMethod (to-one, type PaymentMethod, via CreditMemoPart.Account.DefaultPaymentMethod)
- Invoice (to-one, via CreditMemoPart.Invoice)
- ParentAccount (to-one, type Account, via CreditMemoPart.Account.ParentAccount)
- ShipToContact (to-one, type Contact, via CreditMemoPart.Account.ShipToContact)
- SoldToContact (to-one, type Contact, via CreditMemoPart.Account.SoldToContact)

**Referenced by:** none

## CreditMemoPartItem

**References (foreign keys / relations):**
- Account (to-one, via CreditMemoPartItem.CreditMemoPart.Account)
- BillToContact (to-one, type Contact, via CreditMemoPartItem.CreditMemoPart.Account.BillToContact)
- CreditMemo (to-one, via CreditMemoPartItem.CreditMemoPart.CreditMemo)
- CreditMemoItem (to-one, via CreditMemoPartItem.CreditMemoItem)
- CreditMemoPart (to-one, via CreditMemoPartItem.CreditMemoPart)
- CreditTaxationItem (to-one, via CreditMemoPartItem.CreditTaxationItem)
- DebitMemo (to-one, via CreditMemoPartItem.CreditMemoPart.DebitMemo)
- DebitMemoItem (to-one, via CreditMemoPartItem.DebitMemoItem)
- DebitTaxationItem (to-one, via CreditMemoPartItem.DebitTaxationItem)
- DefaultPaymentMethod (to-one, type PaymentMethod, via CreditMemoPartItem.CreditMemoPart.Account.DefaultPaymentMethod)
- Invoice (to-one, via CreditMemoPartItem.CreditMemoPart.Invoice)
- InvoiceItem (to-one, via CreditMemoPartItem.InvoiceItem)
- ParentAccount (to-one, type Account, via CreditMemoPartItem.CreditMemoPart.Account.ParentAccount)
- ShipToContact (to-one, type Contact, via CreditMemoPartItem.CreditMemoPart.Account.ShipToContact)
- SoldToContact (to-one, type Contact, via CreditMemoPartItem.CreditMemoPart.Account.SoldToContact)
- TaxationItem (to-one, via CreditMemoPartItem.TaxationItem)

**Referenced by:** none

## CreditTaxationItem

**References (foreign keys / relations):**
- Account (to-one, via CreditTaxationItem.CreditMemoItem.CreditMemo.Account)
- AccountingPeriod (to-one, via CreditTaxationItem.JournalEntry.AccountingPeriod)
- AccountReceivableAccountingCode (to-one, type AccountingCode, via CreditTaxationItem.AccountReceivableAccountingCode)
- Amendment (to-one, via CreditTaxationItem.CreditMemoItem.RatePlanCharge.RatePlan.Amendment)
- BillToContact (to-one, type Contact, via CreditTaxationItem.CreditMemoItem.CreditMemo.Account.BillToContact)
- CreditMemo (to-one, via CreditTaxationItem.CreditMemoItem.CreditMemo)
- CreditMemoBillToContact (to-one, type Contact, via CreditTaxationItem.CreditMemoItem.CreditMemo.CreditMemoBillToContact)
- CreditMemoItem (to-one, via CreditTaxationItem.CreditMemoItem)
- DebitMemo (to-one, via CreditTaxationItem.CreditMemoItem.CreditMemo.DebitMemo)
- DefaultPaymentMethod (to-one, type PaymentMethod, via CreditTaxationItem.CreditMemoItem.CreditMemo.Account.DefaultPaymentMethod)
- Invoice (to-one, via CreditTaxationItem.CreditMemoItem.CreditMemo.Invoice)
- JournalEntry (to-one, via CreditTaxationItem.JournalEntry)
- JournalRun (to-one, via CreditTaxationItem.JournalEntry.JournalRun)
- OnAccountAccountingCode (to-one, type AccountingCode, via CreditTaxationItem.OnAccountAccountingCode)
- OrderLineItem (to-one, via CreditTaxationItem.CreditMemoItem.OrderLineItem)
- ParentAccount (to-one, type Account, via CreditTaxationItem.CreditMemoItem.CreditMemo.Account.ParentAccount)
- Product (to-one, via CreditTaxationItem.CreditMemoItem.ProductRatePlanCharge.ProductRatePlan.Product)
- ProductRatePlan (to-one, via CreditTaxationItem.CreditMemoItem.ProductRatePlanCharge.ProductRatePlan)
- ProductRatePlanCharge (to-one, via CreditTaxationItem.CreditMemoItem.ProductRatePlanCharge)
- RatePlan (to-one, via CreditTaxationItem.CreditMemoItem.RatePlanCharge.RatePlan)
- RatePlanCharge (to-one, via CreditTaxationItem.CreditMemoItem.RatePlanCharge)
- SalesTaxPayableAccountingCode (to-one, type AccountingCode, via CreditTaxationItem.SalesTaxPayableAccountingCode)
- ShipToContact (to-one, type Contact, via CreditTaxationItem.CreditMemoItem.CreditMemo.Account.ShipToContact)
- SoldToContact (to-one, type Contact, via CreditTaxationItem.CreditMemoItem.CreditMemo.Account.SoldToContact)
- Subscription (to-one, via CreditTaxationItem.CreditMemoItem.Subscription)
- TaxationItem (to-one, via CreditTaxationItem.TaxationItem)

**Referenced by:** none

## DailyConsumptionSummary

**References (foreign keys / relations):**
- FundId -> Fund (to-one)
- RatePlanChargeId -> RatePlanCharge (to-one)
- Account (to-one, via DailyConsumptionSummary.RatePlanCharge.Account)
- Amendment (to-one, via DailyConsumptionSummary.RatePlanCharge.RatePlan.Amendment)
- BillToContact (to-one, type Contact, via DailyConsumptionSummary.RatePlanCharge.Account.BillToContact)
- DefaultPaymentMethod (to-one, type PaymentMethod, via DailyConsumptionSummary.RatePlanCharge.Account.DefaultPaymentMethod)
- InvoiceOwner (to-one, type Account, via DailyConsumptionSummary.RatePlanCharge.InvoiceOwner)
- ParentAccount (to-one, type Account, via DailyConsumptionSummary.RatePlanCharge.Account.ParentAccount)
- PrepaidBalance (to-one, via DailyConsumptionSummary.Fund.PrepaidBalance)
- Product (to-one, via DailyConsumptionSummary.RatePlanCharge.RatePlan.ProductRatePlan.Product)
- ProductRatePlan (to-one, via DailyConsumptionSummary.RatePlanCharge.RatePlan.ProductRatePlan)
- ProductRatePlanCharge (to-one, via DailyConsumptionSummary.RatePlanCharge.ProductRatePlanCharge)
- RatePlan (to-one, via DailyConsumptionSummary.RatePlanCharge.RatePlan)
- ShipToContact (to-one, type Contact, via DailyConsumptionSummary.RatePlanCharge.Account.ShipToContact)
- SoldToContact (to-one, type Contact, via DailyConsumptionSummary.RatePlanCharge.Account.SoldToContact)
- Subscription (to-one, via DailyConsumptionSummary.Fund.PrepaidBalance.Subscription)
- ValidityPeriodSummary (to-one, via DailyConsumptionSummary.Fund.ValidityPeriodSummary)

**Referenced by:** none

## DebitMemo

**References (foreign keys / relations):**
- Account (to-one, via DebitMemo.Account)
- BillingDocumentPDFGeneration (to-one, via DebitMemo.BillingDocumentPDFGeneration)
- BillToContact (to-one, type Contact, via DebitMemo.Account.BillToContact)
- BillToContactSnapshot (to-one, type ContactSnapshot, via DebitMemo.BillToContactSnapshot)
- CreditMemo (to-one, via DebitMemo.CreditMemo)
- DebitMemoBillToContact (to-one, type Contact, via DebitMemo.DebitMemoBillToContact)
- DebitMemoSoldToContact (to-one, type Contact, via DebitMemo.DebitMemoSoldToContact)
- DefaultPaymentMethod (to-one, type PaymentMethod, via DebitMemo.Account.DefaultPaymentMethod)
- EInvoiceProfile (to-one, via DebitMemo.Account.EInvoiceProfile)
- Invoice (to-one, via DebitMemo.Invoice)
- ParentAccount (to-one, type Account, via DebitMemo.Account.ParentAccount)
- ShipToContact (to-one, type Contact, via DebitMemo.Account.ShipToContact)
- ShipToContactSnapshot (to-one, type ContactSnapshot, via DebitMemo.ShipToContactSnapshot)
- SoldToContact (to-one, type Contact, via DebitMemo.Account.SoldToContact)
- SoldToContactSnapshot (to-one, type ContactSnapshot, via DebitMemo.SoldToContactSnapshot)

**Referenced by:** none

## DebitMemoItem

**References (foreign keys / relations):**
- Account (to-one, via DebitMemoItem.DebitMemo.Account)
- AccountingPeriod (to-one, via DebitMemoItem.JournalEntry.AccountingPeriod)
- AccountReceivableAccountingCode (to-one, type AccountingCode, via DebitMemoItem.AccountReceivableAccountingCode)
- Amendment (to-one, via DebitMemoItem.RatePlanCharge.RatePlan.Amendment)
- BillToContact (to-one, type Contact, via DebitMemoItem.DebitMemo.Account.BillToContact)
- BillToContactSnapshot (to-one, type ContactSnapshot, via DebitMemoItem.DebitMemo.BillToContactSnapshot)
- CreditMemo (to-one, via DebitMemoItem.DebitMemo.CreditMemo)
- CreditMemoItem (to-one, via DebitMemoItem.CreditMemoItem)
- DebitMemo (to-one, via DebitMemoItem.DebitMemo)
- DebitMemoBillToContact (to-one, type Contact, via DebitMemoItem.DebitMemo.DebitMemoBillToContact)
- DebitMemoItemShipToContact (to-one, type Contact, via DebitMemoItem.DebitMemoItemShipToContact)
- DebitMemoItemSoldToContact (to-one, type Contact, via DebitMemoItem.DebitMemoItemSoldToContact)
- DebitMemoItemSoldToContactSnapshot (to-one, type ContactSnapshot, via DebitMemoItem.DebitMemoItemSoldToContactSnapshot)
- DefaultPaymentMethod (to-one, type PaymentMethod, via DebitMemoItem.DebitMemo.Account.DefaultPaymentMethod)
- DeferredRevenueAccountingCode (to-one, type AccountingCode, via DebitMemoItem.DeferredRevenueAccountingCode)
- Invoice (to-one, via DebitMemoItem.InvoiceItem.Invoice)
- InvoiceItem (to-one, via DebitMemoItem.InvoiceItem)
- JournalEntry (to-one, via DebitMemoItem.JournalEntry)
- JournalRun (to-one, via DebitMemoItem.JournalEntry.JournalRun)
- OrderLineItem (to-one, via DebitMemoItem.OrderLineItem)
- ParentAccount (to-one, type Account, via DebitMemoItem.DebitMemo.Account.ParentAccount)
- Product (to-one, via DebitMemoItem.ProductRatePlanCharge.ProductRatePlan.Product)
- ProductRatePlan (to-one, via DebitMemoItem.ProductRatePlanCharge.ProductRatePlan)
- ProductRatePlanCharge (to-one, via DebitMemoItem.ProductRatePlanCharge)
- RatePlan (to-one, via DebitMemoItem.RatePlanCharge.RatePlan)
- RatePlanCharge (to-one, via DebitMemoItem.RatePlanCharge)
- RecognizedRevenueAccountingCode (to-one, type AccountingCode, via DebitMemoItem.RecognizedRevenueAccountingCode)
- ShipToContact (to-one, type Contact, via DebitMemoItem.DebitMemo.Account.ShipToContact)
- ShipToContactSnapshot (to-one, type ContactSnapshot, via DebitMemoItem.DebitMemo.ShipToContactSnapshot)
- SoldToContact (to-one, type Contact, via DebitMemoItem.DebitMemo.Account.SoldToContact)
- SoldToContactSnapshot (to-one, type ContactSnapshot, via DebitMemoItem.DebitMemo.SoldToContactSnapshot)
- Subscription (to-one, via DebitMemoItem.Subscription)

**Referenced by:** none

## DebitTaxationItem

**References (foreign keys / relations):**
- Account (to-one, via DebitTaxationItem.DebitMemoItem.DebitMemo.Account)
- AccountingPeriod (to-one, via DebitTaxationItem.JournalEntry.AccountingPeriod)
- AccountReceivableAccountingCode (to-one, type AccountingCode, via DebitTaxationItem.AccountReceivableAccountingCode)
- Amendment (to-one, via DebitTaxationItem.DebitMemoItem.RatePlanCharge.RatePlan.Amendment)
- BillToContact (to-one, type Contact, via DebitTaxationItem.DebitMemoItem.DebitMemo.Account.BillToContact)
- CreditMemo (to-one, via DebitTaxationItem.DebitMemoItem.DebitMemo.CreditMemo)
- CreditTaxationItem (to-one, via DebitTaxationItem.CreditTaxationItem)
- DebitMemo (to-one, via DebitTaxationItem.DebitMemoItem.DebitMemo)
- DebitMemoItem (to-one, via DebitTaxationItem.DebitMemoItem)
- DefaultPaymentMethod (to-one, type PaymentMethod, via DebitTaxationItem.DebitMemoItem.DebitMemo.Account.DefaultPaymentMethod)
- Invoice (to-one, via DebitTaxationItem.DebitMemoItem.DebitMemo.Invoice)
- JournalEntry (to-one, via DebitTaxationItem.JournalEntry)
- JournalRun (to-one, via DebitTaxationItem.JournalEntry.JournalRun)
- OrderLineItem (to-one, via DebitTaxationItem.DebitMemoItem.OrderLineItem)
- ParentAccount (to-one, type Account, via DebitTaxationItem.DebitMemoItem.DebitMemo.Account.ParentAccount)
- Product (to-one, via DebitTaxationItem.DebitMemoItem.ProductRatePlanCharge.ProductRatePlan.Product)
- ProductRatePlan (to-one, via DebitTaxationItem.DebitMemoItem.ProductRatePlanCharge.ProductRatePlan)
- ProductRatePlanCharge (to-one, via DebitTaxationItem.DebitMemoItem.ProductRatePlanCharge)
- RatePlan (to-one, via DebitTaxationItem.DebitMemoItem.RatePlanCharge.RatePlan)
- RatePlanCharge (to-one, via DebitTaxationItem.DebitMemoItem.RatePlanCharge)
- SalesTaxPayableAccountingCode (to-one, type AccountingCode, via DebitTaxationItem.SalesTaxPayableAccountingCode)
- ShipToContact (to-one, type Contact, via DebitTaxationItem.DebitMemoItem.DebitMemo.Account.ShipToContact)
- SoldToContact (to-one, type Contact, via DebitTaxationItem.DebitMemoItem.DebitMemo.Account.SoldToContact)
- Subscription (to-one, via DebitTaxationItem.DebitMemoItem.Subscription)
- TaxationItem (to-one, via DebitTaxationItem.TaxationItem)

**Referenced by:** none

## DeliveryAdjustment

**References (foreign keys / relations):**
- AccountId -> Account (to-one)
- SubscriptionId -> Subscription (to-one)
- BillToContact (to-one, type Contact, via DeliveryAdjustment.Account.BillToContact)
- DefaultPaymentMethod (to-one, type PaymentMethod, via DeliveryAdjustment.Account.DefaultPaymentMethod)
- ParentAccount (to-one, type Account, via DeliveryAdjustment.Account.ParentAccount)
- RatePlan (to-one, via DeliveryAdjustment.RatePlanCharge.RatePlan)
- RatePlanCharge (to-one, via DeliveryAdjustment.RatePlanCharge)
- ShipToContact (to-one, type Contact, via DeliveryAdjustment.Account.ShipToContact)
- SoldToContact (to-one, type Contact, via DeliveryAdjustment.Account.SoldToContact)

**Referenced by:** none

## DiscountApplyDetail

**References:** none

**Referenced by:** none

## DiscountClass

**References:** none

**Referenced by:**
- ProductRatePlanCharge.DiscountClassId

## EmailHistory

**References (foreign keys / relations):**
- Account (to-one, via EmailHistory.Account)
- BillToContact (to-one, type Contact, via EmailHistory.Account.BillToContact)
- DefaultPaymentMethod (to-one, type PaymentMethod, via EmailHistory.Account.DefaultPaymentMethod)
- ParentAccount (to-one, type Account, via EmailHistory.Account.ParentAccount)
- ShipToContact (to-one, type Contact, via EmailHistory.Account.ShipToContact)
- SoldToContact (to-one, type Contact, via EmailHistory.Account.SoldToContact)

**Referenced by:** none

## Export

**References:** none

**Referenced by:** none

## Fulfillment

**References (foreign keys / relations):**
- OrderLineItem (to-one, via Fulfillment.OrderLineItem)

**Referenced by:** none

## FulfillmentItem

**References (foreign keys / relations):**
- Fulfillment (to-one, via FulfillmentItem.Fulfillment)

**Referenced by:** none

## Fund

**References (foreign keys / relations):**
- AccountId -> Account (to-one)
- PrepaidBalanceId -> PrepaidBalance (to-one)
- RatePlanChargeId -> RatePlanCharge (to-one)
- ValidityPeriodSummaryId -> ValidityPeriodSummary (to-one)
- Amendment (to-one, via Fund.RatePlanCharge.RatePlan.Amendment)
- BillToContact (to-one, type Contact, via Fund.Account.BillToContact)
- DefaultPaymentMethod (to-one, type PaymentMethod, via Fund.Account.DefaultPaymentMethod)
- ParentAccount (to-one, type Account, via Fund.Account.ParentAccount)
- Product (to-one, via Fund.RatePlanCharge.RatePlan.ProductRatePlan.Product)
- ProductRatePlan (to-one, via Fund.RatePlanCharge.RatePlan.ProductRatePlan)
- ProductRatePlanCharge (to-one, via Fund.RatePlanCharge.ProductRatePlanCharge)
- RatePlan (to-one, via Fund.RatePlanCharge.RatePlan)
- ShipToContact (to-one, type Contact, via Fund.Account.ShipToContact)
- SoldToContact (to-one, type Contact, via Fund.Account.SoldToContact)
- Subscription (to-one, via Fund.PrepaidBalance.Subscription)

**Referenced by:**
- DailyConsumptionSummary.FundId

## GatewayProfileData

**References:** none

**Referenced by:** none

## GuidedUsage

**References (foreign keys / relations):**
- Account (to-one, via GuidedUsage.Usage.Account)
- Amendment (to-one, via GuidedUsage.RatePlanCharge.RatePlan.Amendment)
- BillToContact (to-one, type Contact, via GuidedUsage.Usage.Account.BillToContact)
- DefaultPaymentMethod (to-one, type PaymentMethod, via GuidedUsage.Usage.Account.DefaultPaymentMethod)
- ParentAccount (to-one, type Account, via GuidedUsage.Usage.Account.ParentAccount)
- Product (to-one, via GuidedUsage.RatePlanCharge.RatePlan.ProductRatePlan.Product)
- ProductRatePlan (to-one, via GuidedUsage.RatePlanCharge.RatePlan.ProductRatePlan)
- ProductRatePlanCharge (to-one, via GuidedUsage.RatePlanCharge.ProductRatePlanCharge)
- RatePlan (to-one, via GuidedUsage.RatePlanCharge.RatePlan)
- RatePlanCharge (to-one, via GuidedUsage.RatePlanCharge)
- ShipToContact (to-one, type Contact, via GuidedUsage.Usage.Account.ShipToContact)
- SoldToContact (to-one, type Contact, via GuidedUsage.Usage.Account.SoldToContact)
- Subscription (to-one, via GuidedUsage.Subscription)
- Usage (to-one, via GuidedUsage.Usage)

**Referenced by:** none

## HpmCaptchaValidationResult

**References (foreign keys / relations):**
- Account (to-one, via HpmCaptchaValidationResult.PaymentMethodTransactionLog.Account)
- BillToContact (to-one, type Contact, via HpmCaptchaValidationResult.PaymentMethodTransactionLog.Account.BillToContact)
- DefaultPaymentMethod (to-one, type PaymentMethod, via HpmCaptchaValidationResult.PaymentMethodTransactionLog.Account.DefaultPaymentMethod)
- ParentAccount (to-one, type Account, via HpmCaptchaValidationResult.PaymentMethodTransactionLog.Account.ParentAccount)
- PaymentMethod (to-one, via HpmCaptchaValidationResult.PaymentMethodTransactionLog.PaymentMethod)
- PaymentMethodTransactionLog (to-one, via HpmCaptchaValidationResult.PaymentMethodTransactionLog)
- ShipToContact (to-one, type Contact, via HpmCaptchaValidationResult.PaymentMethodTransactionLog.Account.ShipToContact)
- SoldToContact (to-one, type Contact, via HpmCaptchaValidationResult.PaymentMethodTransactionLog.Account.SoldToContact)

**Referenced by:** none

## Import

**References:** none

**Referenced by:** none

## Invoice

**References (foreign keys / relations):**
- AccountId -> Account (to-one)
- BillToContactId -> Contact (to-one, as BillToContact)
- BillToContactSnapshotId -> ContactSnapshot (to-one, as BillToContactSnapshot)
- SoldToContactId -> Contact (to-one, as SoldToContact)
- SoldToContactSnapshotId -> ContactSnapshot (to-one, as SoldToContactSnapshot)
- BillingDocumentPDFGeneration (to-one, via Invoice.BillingDocumentPDFGeneration)
- DefaultPaymentMethod (to-one, type PaymentMethod, via Invoice.Account.DefaultPaymentMethod)
- EInvoiceProfile (to-one, via Invoice.Account.EInvoiceProfile)
- InvoiceBillToContact (to-one, type Contact, via Invoice.InvoiceBillToContact)
- InvoiceShipToContact (to-one, type Contact, via Invoice.InvoiceShipToContact)
- InvoiceSoldToContact (to-one, type Contact, via Invoice.InvoiceSoldToContact)
- ParentAccount (to-one, type Account, via Invoice.Account.ParentAccount)
- ShipToContact (to-one, type Contact, via Invoice.Account.ShipToContact)
- ShipToContactSnapshot (to-one, type ContactSnapshot, via Invoice.ShipToContactSnapshot)

**Referenced by:**
- InvoiceAdjustment.InvoiceId
- InvoiceItem.InvoiceId
- InvoiceItemAdjustment.InvoiceId
- InvoicePayment.InvoiceId
- PaymentPart.InvoiceId
- RefundInvoicePayment.InvoiceId
- TaxationItem.InvoiceId

## InvoiceAdjustment

**References (foreign keys / relations):**
- AccountId -> Account (to-one)
- InvoiceId -> Invoice (to-one)
- AccountingPeriod (to-one, via InvoiceAdjustment.JournalEntry.AccountingPeriod)
- AccountReceivableAccountingCode (to-one, type AccountingCode, via InvoiceAdjustment.AccountReceivableAccountingCode)
- BillToContact (to-one, type Contact, via InvoiceAdjustment.Account.BillToContact)
- DefaultPaymentMethod (to-one, type PaymentMethod, via InvoiceAdjustment.Account.DefaultPaymentMethod)
- DeferredRevenueAccountingCode (to-one, type AccountingCode, via InvoiceAdjustment.DeferredRevenueAccountingCode)
- JournalEntry (to-one, via InvoiceAdjustment.JournalEntry)
- JournalRun (to-one, via InvoiceAdjustment.JournalEntry.JournalRun)
- ParentAccount (to-one, type Account, via InvoiceAdjustment.Account.ParentAccount)
- ShipToContact (to-one, type Contact, via InvoiceAdjustment.Account.ShipToContact)
- SoldToContact (to-one, type Contact, via InvoiceAdjustment.Account.SoldToContact)

**Referenced by:** none

## InvoiceItem

**References (foreign keys / relations):**
- InvoiceId -> Invoice (to-one)
- ProductId -> Product (to-one)
- RatePlanChargeId -> RatePlanCharge (to-one)
- SubscriptionId -> Subscription (to-one)
- Account (to-one, via InvoiceItem.Invoice.Account)
- AccountingPeriod (to-one, via InvoiceItem.JournalEntry.AccountingPeriod)
- AccountReceivableAccountingCode (to-one, type AccountingCode, via InvoiceItem.AccountReceivableAccountingCode)
- AdjustmentLiabilityAccountingCode (to-one, type AccountingCode, via InvoiceItem.AdjustmentLiabilityAccountingCode)
- AdjustmentRevenueAccountingCode (to-one, type AccountingCode, via InvoiceItem.AdjustmentRevenueAccountingCode)
- Amendment (to-one, via InvoiceItem.RatePlanCharge.RatePlan.Amendment)
- BillToContact (to-one, type Contact, via InvoiceItem.Invoice.Account.BillToContact)
- BillToContactSnapshot (to-one, type ContactSnapshot, via InvoiceItem.Invoice.BillToContactSnapshot)
- ContractAssetAccountingCode (to-one, type AccountingCode, via InvoiceItem.ContractAssetAccountingCode)
- ContractLiabilityAccountingCode (to-one, type AccountingCode, via InvoiceItem.ContractLiabilityAccountingCode)
- ContractRecognizedRevenueAccountingCode (to-one, type AccountingCode, via InvoiceItem.ContractRecognizedRevenueAccountingCode)
- DefaultPaymentMethod (to-one, type PaymentMethod, via InvoiceItem.Invoice.Account.DefaultPaymentMethod)
- DeferredRevenueAccountingCode (to-one, type AccountingCode, via InvoiceItem.DeferredRevenueAccountingCode)
- Fulfillment (to-one, via InvoiceItem.Fulfillment)
- InvoiceBillToContact (to-one, type Contact, via InvoiceItem.Invoice.InvoiceBillToContact)
- InvoiceItemShipToContact (to-one, type Contact, via InvoiceItem.InvoiceItemShipToContact)
- InvoiceItemSoldToContact (to-one, type Contact, via InvoiceItem.InvoiceItemSoldToContact)
- InvoiceItemSoldToContactSnapshot (to-one, type ContactSnapshot, via InvoiceItem.InvoiceItemSoldToContactSnapshot)
- InvoiceShipToContact (to-one, type Contact, via InvoiceItem.Invoice.InvoiceShipToContact)
- InvoiceSoldToContact (to-one, type Contact, via InvoiceItem.Invoice.InvoiceSoldToContact)
- JournalEntry (to-one, via InvoiceItem.JournalEntry)
- JournalRun (to-one, via InvoiceItem.JournalEntry.JournalRun)
- OrderLineItem (to-one, via InvoiceItem.OrderLineItem)
- ParentAccount (to-one, type Account, via InvoiceItem.Invoice.Account.ParentAccount)
- ProductRatePlan (to-one, via InvoiceItem.ProductRatePlanCharge.ProductRatePlan)
- ProductRatePlanCharge (to-one, via InvoiceItem.ProductRatePlanCharge)
- RatePlan (to-one, via InvoiceItem.RatePlanCharge.RatePlan)
- RecognizedRevenueAccountingCode (to-one, type AccountingCode, via InvoiceItem.RecognizedRevenueAccountingCode)
- ShipToContact (to-one, type Contact, via InvoiceItem.Invoice.Account.ShipToContact)
- ShipToContactSnapshot (to-one, type ContactSnapshot, via InvoiceItem.Invoice.ShipToContactSnapshot)
- SoldToContact (to-one, type Contact, via InvoiceItem.Invoice.Account.SoldToContact)
- SoldToContactSnapshot (to-one, type ContactSnapshot, via InvoiceItem.Invoice.SoldToContactSnapshot)
- UnbilledReceivablesAccountingCode (to-one, type AccountingCode, via InvoiceItem.UnbilledReceivablesAccountingCode)

**Referenced by:**
- ProcessedUsage.InvoiceItemId
- TaxationItem.InvoiceItemId

## InvoiceItemAdjustment

**References (foreign keys / relations):**
- AccountId -> Account (to-one)
- InvoiceId -> Invoice (to-one)
- AccountingPeriod (to-one, via InvoiceItemAdjustment.JournalEntry.AccountingPeriod)
- AccountReceivableAccountingCode (to-one, type AccountingCode, via InvoiceItemAdjustment.AccountReceivableAccountingCode)
- Amendment (to-one, via InvoiceItemAdjustment.InvoiceItem.RatePlanCharge.RatePlan.Amendment)
- BillToContact (to-one, type Contact, via InvoiceItemAdjustment.Invoice.Account.BillToContact)
- BillToContactSnapshot (to-one, type ContactSnapshot, via InvoiceItemAdjustment.Invoice.BillToContactSnapshot)
- DefaultPaymentMethod (to-one, type PaymentMethod, via InvoiceItemAdjustment.Invoice.Account.DefaultPaymentMethod)
- DeferredRevenueAccountingCode (to-one, type AccountingCode, via InvoiceItemAdjustment.DeferredRevenueAccountingCode)
- InvoiceItem (to-one, via InvoiceItemAdjustment.InvoiceItem)
- JournalEntry (to-one, via InvoiceItemAdjustment.JournalEntry)
- JournalRun (to-one, via InvoiceItemAdjustment.JournalEntry.JournalRun)
- ParentAccount (to-one, type Account, via InvoiceItemAdjustment.Invoice.Account.ParentAccount)
- Product (to-one, via InvoiceItemAdjustment.InvoiceItem.RatePlanCharge.RatePlan.ProductRatePlan.Product)
- ProductRatePlan (to-one, via InvoiceItemAdjustment.InvoiceItem.RatePlanCharge.RatePlan.ProductRatePlan)
- ProductRatePlanCharge (to-one, via InvoiceItemAdjustment.InvoiceItem.RatePlanCharge.ProductRatePlanCharge)
- RatePlan (to-one, via InvoiceItemAdjustment.InvoiceItem.RatePlanCharge.RatePlan)
- RatePlanCharge (to-one, via InvoiceItemAdjustment.InvoiceItem.RatePlanCharge)
- RecognizedRevenueAccountingCode (to-one, type AccountingCode, via InvoiceItemAdjustment.RecognizedRevenueAccountingCode)
- SalesTaxPayableAccountingCode (to-one, type AccountingCode, via InvoiceItemAdjustment.SalesTaxPayableAccountingCode)
- ShipToContact (to-one, type Contact, via InvoiceItemAdjustment.Invoice.Account.ShipToContact)
- ShipToContactSnapshot (to-one, type ContactSnapshot, via InvoiceItemAdjustment.Invoice.ShipToContactSnapshot)
- SoldToContact (to-one, type Contact, via InvoiceItemAdjustment.Invoice.Account.SoldToContact)
- SoldToContactSnapshot (to-one, type ContactSnapshot, via InvoiceItemAdjustment.Invoice.SoldToContactSnapshot)
- Subscription (to-one, via InvoiceItemAdjustment.InvoiceItem.RatePlanCharge.RatePlan.Subscription)
- TaxationItem (to-one, via InvoiceItemAdjustment.TaxationItem)

**Referenced by:** none

## InvoicePayment

**References (foreign keys / relations):**
- InvoiceId -> Invoice (to-one)
- PaymentId -> Payment (to-one)
- Account (to-one, via InvoicePayment.Payment.Account)
- AccountingPeriod (to-one, via InvoicePayment.JournalEntry.AccountingPeriod)
- AccountReceivableAccountingCode (to-one, type AccountingCode, via InvoicePayment.AccountReceivableAccountingCode)
- BillToContact (to-one, type Contact, via InvoicePayment.Payment.Account.BillToContact)
- CashAccountingCode (to-one, type AccountingCode, via InvoicePayment.CashAccountingCode)
- DefaultPaymentMethod (to-one, type PaymentMethod, via InvoicePayment.Payment.Account.DefaultPaymentMethod)
- JournalEntry (to-one, via InvoicePayment.JournalEntry)
- JournalRun (to-one, via InvoicePayment.JournalEntry.JournalRun)
- ParentAccount (to-one, type Account, via InvoicePayment.Payment.Account.ParentAccount)
- PaymentMethod (to-one, via InvoicePayment.Payment.PaymentMethod)
- PaymentMethodSnapshot (to-one, via InvoicePayment.Payment.PaymentMethodSnapshot)
- ShipToContact (to-one, type Contact, via InvoicePayment.Payment.Account.ShipToContact)
- SoldToContact (to-one, type Contact, via InvoicePayment.Payment.Account.SoldToContact)

**Referenced by:**
- RefundInvoicePayment.InvoicePaymentId

## InvoiceSplit

**References:** none

**Referenced by:** none

## InvoiceSplitItem

**References:** none

**Referenced by:** none

## JournalEntry

**References (foreign keys / relations):**
- AccountingPeriod (to-one, via JournalEntry.AccountingPeriod)
- JournalRun (to-one, via JournalEntry.JournalRun)

**Referenced by:** none

## JournalEntryDetailCreditBalanceAdjustment

**References (foreign keys / relations):**
- CreditAccountingCode (to-one, type AccountingCode, via JournalEntryDetailCreditBalanceAdjustment.CreditAccountingCode)
- DebitAccountingCode (to-one, type AccountingCode, via JournalEntryDetailCreditBalanceAdjustment.DebitAccountingCode)
- JournalEntry (to-one, via JournalEntryDetailCreditBalanceAdjustment.JournalEntry)
- JournalRun (to-one, via JournalEntryDetailCreditBalanceAdjustment.JournalEntry.JournalRun)

**Referenced by:** none

## JournalEntryDetailCreditMemoApplicationItem

**References (foreign keys / relations):**
- CreditAccountingCode (to-one, type AccountingCode, via JournalEntryDetailCreditMemoApplicationItem.CreditAccountingCode)
- DebitAccountingCode (to-one, type AccountingCode, via JournalEntryDetailCreditMemoApplicationItem.DebitAccountingCode)
- JournalEntry (to-one, via JournalEntryDetailCreditMemoApplicationItem.JournalEntry)
- JournalRun (to-one, via JournalEntryDetailCreditMemoApplicationItem.JournalEntry.JournalRun)

**Referenced by:** none

## JournalEntryDetailCreditMemoItem

**References (foreign keys / relations):**
- CreditAccountingCode (to-one, type AccountingCode, via JournalEntryDetailCreditMemoItem.CreditAccountingCode)
- DebitAccountingCode (to-one, type AccountingCode, via JournalEntryDetailCreditMemoItem.DebitAccountingCode)
- JournalEntry (to-one, via JournalEntryDetailCreditMemoItem.JournalEntry)
- JournalRun (to-one, via JournalEntryDetailCreditMemoItem.JournalEntry.JournalRun)

**Referenced by:** none

## JournalEntryDetailCreditTaxationItem

**References (foreign keys / relations):**
- CreditAccountingCode (to-one, type AccountingCode, via JournalEntryDetailCreditTaxationItem.CreditAccountingCode)
- DebitAccountingCode (to-one, type AccountingCode, via JournalEntryDetailCreditTaxationItem.DebitAccountingCode)
- JournalEntry (to-one, via JournalEntryDetailCreditTaxationItem.JournalEntry)
- JournalRun (to-one, via JournalEntryDetailCreditTaxationItem.JournalEntry.JournalRun)

**Referenced by:** none

## JournalEntryDetailDebitMemoItem

**References (foreign keys / relations):**
- CreditAccountingCode (to-one, type AccountingCode, via JournalEntryDetailDebitMemoItem.CreditAccountingCode)
- DebitAccountingCode (to-one, type AccountingCode, via JournalEntryDetailDebitMemoItem.DebitAccountingCode)
- JournalEntry (to-one, via JournalEntryDetailDebitMemoItem.JournalEntry)
- JournalRun (to-one, via JournalEntryDetailDebitMemoItem.JournalEntry.JournalRun)

**Referenced by:** none

## JournalEntryDetailDebitTaxationItem

**References (foreign keys / relations):**
- CreditAccountingCode (to-one, type AccountingCode, via JournalEntryDetailDebitTaxationItem.CreditAccountingCode)
- DebitAccountingCode (to-one, type AccountingCode, via JournalEntryDetailDebitTaxationItem.DebitAccountingCode)
- JournalEntry (to-one, via JournalEntryDetailDebitTaxationItem.JournalEntry)
- JournalRun (to-one, via JournalEntryDetailDebitTaxationItem.JournalEntry.JournalRun)

**Referenced by:** none

## JournalEntryDetailFXGainLoss

**References (foreign keys / relations):**
- AccountId -> Account (to-one)
- BillToContact (to-one, type Contact, via JournalEntryDetailFXGainLoss.Account.BillToContact)
- CreditAccountingCode (to-one, type AccountingCode, via JournalEntryDetailFXGainLoss.CreditAccountingCode)
- CreditMemo (to-one, via JournalEntryDetailFXGainLoss.CreditMemo)
- CreditMemoItem (to-one, via JournalEntryDetailFXGainLoss.CreditMemoItem)
- CreditTaxationItem (to-one, via JournalEntryDetailFXGainLoss.CreditTaxationItem)
- DebitAccountingCode (to-one, type AccountingCode, via JournalEntryDetailFXGainLoss.DebitAccountingCode)
- DebitMemo (to-one, via JournalEntryDetailFXGainLoss.DebitMemo)
- DebitMemoItem (to-one, via JournalEntryDetailFXGainLoss.DebitMemoItem)
- DebitTaxationItem (to-one, via JournalEntryDetailFXGainLoss.DebitTaxationItem)
- DefaultPaymentMethod (to-one, type PaymentMethod, via JournalEntryDetailFXGainLoss.Account.DefaultPaymentMethod)
- Invoice (to-one, via JournalEntryDetailFXGainLoss.Invoice)
- InvoiceItem (to-one, via JournalEntryDetailFXGainLoss.InvoiceItem)
- JournalEntry (to-one, via JournalEntryDetailFXGainLoss.JournalEntry)
- JournalRun (to-one, via JournalEntryDetailFXGainLoss.JournalEntry.JournalRun)
- ParentAccount (to-one, type Account, via JournalEntryDetailFXGainLoss.Account.ParentAccount)
- Payment (to-one, via JournalEntryDetailFXGainLoss.Payment)
- PaymentApplication (to-one, via JournalEntryDetailFXGainLoss.PaymentApplication)
- PaymentApplicationItem (to-one, via JournalEntryDetailFXGainLoss.PaymentApplicationItem)
- PaymentMethod (to-one, via JournalEntryDetailFXGainLoss.Payment.PaymentMethod)
- PaymentMethodSnapshot (to-one, via JournalEntryDetailFXGainLoss.Payment.PaymentMethodSnapshot)
- Refund (to-one, via JournalEntryDetailFXGainLoss.Refund)
- RefundApplication (to-one, via JournalEntryDetailFXGainLoss.RefundApplication)
- RefundApplicationItem (to-one, via JournalEntryDetailFXGainLoss.RefundApplicationItem)
- ShipToContact (to-one, type Contact, via JournalEntryDetailFXGainLoss.Account.ShipToContact)
- SoldToContact (to-one, type Contact, via JournalEntryDetailFXGainLoss.Account.SoldToContact)
- TaxationItem (to-one, via JournalEntryDetailFXGainLoss.TaxationItem)

**Referenced by:** none

## JournalEntryDetailInvoiceAdjustment

**References (foreign keys / relations):**
- CreditAccountingCode (to-one, type AccountingCode, via JournalEntryDetailInvoiceAdjustment.CreditAccountingCode)
- DebitAccountingCode (to-one, type AccountingCode, via JournalEntryDetailInvoiceAdjustment.DebitAccountingCode)
- JournalEntry (to-one, via JournalEntryDetailInvoiceAdjustment.JournalEntry)
- JournalRun (to-one, via JournalEntryDetailInvoiceAdjustment.JournalEntry.JournalRun)

**Referenced by:** none

## JournalEntryDetailInvoiceItem

**References (foreign keys / relations):**
- CreditAccountingCode (to-one, type AccountingCode, via JournalEntryDetailInvoiceItem.CreditAccountingCode)
- DebitAccountingCode (to-one, type AccountingCode, via JournalEntryDetailInvoiceItem.DebitAccountingCode)
- JournalEntry (to-one, via JournalEntryDetailInvoiceItem.JournalEntry)
- JournalRun (to-one, via JournalEntryDetailInvoiceItem.JournalEntry.JournalRun)

**Referenced by:** none

## JournalEntryDetailInvoiceItemAdjustment

**References (foreign keys / relations):**
- CreditAccountingCode (to-one, type AccountingCode, via JournalEntryDetailInvoiceItemAdjustment.CreditAccountingCode)
- DebitAccountingCode (to-one, type AccountingCode, via JournalEntryDetailInvoiceItemAdjustment.DebitAccountingCode)
- JournalEntry (to-one, via JournalEntryDetailInvoiceItemAdjustment.JournalEntry)
- JournalRun (to-one, via JournalEntryDetailInvoiceItemAdjustment.JournalEntry.JournalRun)

**Referenced by:** none

## JournalEntryDetailInvoicePayment

**References (foreign keys / relations):**
- CreditAccountingCode (to-one, type AccountingCode, via JournalEntryDetailInvoicePayment.CreditAccountingCode)
- DebitAccountingCode (to-one, type AccountingCode, via JournalEntryDetailInvoicePayment.DebitAccountingCode)
- JournalEntry (to-one, via JournalEntryDetailInvoicePayment.JournalEntry)
- JournalRun (to-one, via JournalEntryDetailInvoicePayment.JournalEntry.JournalRun)

**Referenced by:** none

## JournalEntryDetailPaymentApplication

**References (foreign keys / relations):**
- CreditAccountingCode (to-one, type AccountingCode, via JournalEntryDetailPaymentApplication.CreditAccountingCode)
- DebitAccountingCode (to-one, type AccountingCode, via JournalEntryDetailPaymentApplication.DebitAccountingCode)
- JournalEntry (to-one, via JournalEntryDetailPaymentApplication.JournalEntry)
- JournalRun (to-one, via JournalEntryDetailPaymentApplication.JournalEntry.JournalRun)

**Referenced by:** none

## JournalEntryDetailPaymentApplicationItem

**References (foreign keys / relations):**
- CreditAccountingCode (to-one, type AccountingCode, via JournalEntryDetailPaymentApplicationItem.CreditAccountingCode)
- DebitAccountingCode (to-one, type AccountingCode, via JournalEntryDetailPaymentApplicationItem.DebitAccountingCode)
- JournalEntry (to-one, via JournalEntryDetailPaymentApplicationItem.JournalEntry)
- JournalRun (to-one, via JournalEntryDetailPaymentApplicationItem.JournalEntry.JournalRun)

**Referenced by:** none

## JournalEntryDetailRealizedFxGainLoss

**References (foreign keys / relations):**
- CreditAccountingCode (to-one, type AccountingCode, via JournalEntryDetailRealizedFxGainLoss.CreditAccountingCode)
- DebitAccountingCode (to-one, type AccountingCode, via JournalEntryDetailRealizedFxGainLoss.DebitAccountingCode)
- JournalEntry (to-one, via JournalEntryDetailRealizedFxGainLoss.JournalEntry)
- JournalRun (to-one, via JournalEntryDetailRealizedFxGainLoss.JournalEntry.JournalRun)

**Referenced by:** none

## JournalEntryDetailRefundApplication

**References (foreign keys / relations):**
- CreditAccountingCode (to-one, type AccountingCode, via JournalEntryDetailRefundApplication.CreditAccountingCode)
- DebitAccountingCode (to-one, type AccountingCode, via JournalEntryDetailRefundApplication.DebitAccountingCode)
- JournalEntry (to-one, via JournalEntryDetailRefundApplication.JournalEntry)
- JournalRun (to-one, via JournalEntryDetailRefundApplication.JournalEntry.JournalRun)

**Referenced by:** none

## JournalEntryDetailRefundApplicationItem

**References (foreign keys / relations):**
- CreditAccountingCode (to-one, type AccountingCode, via JournalEntryDetailRefundApplicationItem.CreditAccountingCode)
- DebitAccountingCode (to-one, type AccountingCode, via JournalEntryDetailRefundApplicationItem.DebitAccountingCode)
- JournalEntry (to-one, via JournalEntryDetailRefundApplicationItem.JournalEntry)
- JournalRun (to-one, via JournalEntryDetailRefundApplicationItem.JournalEntry.JournalRun)

**Referenced by:** none

## JournalEntryDetailRefundInvoicePayment

**References (foreign keys / relations):**
- CreditAccountingCode (to-one, type AccountingCode, via JournalEntryDetailRefundInvoicePayment.CreditAccountingCode)
- DebitAccountingCode (to-one, type AccountingCode, via JournalEntryDetailRefundInvoicePayment.DebitAccountingCode)
- JournalEntry (to-one, via JournalEntryDetailRefundInvoicePayment.JournalEntry)
- JournalRun (to-one, via JournalEntryDetailRefundInvoicePayment.JournalEntry.JournalRun)

**Referenced by:** none

## JournalEntryDetailRevenueEventItem

**References (foreign keys / relations):**
- CreditAccountingCode (to-one, type AccountingCode, via JournalEntryDetailRevenueEventItem.CreditAccountingCode)
- DebitAccountingCode (to-one, type AccountingCode, via JournalEntryDetailRevenueEventItem.DebitAccountingCode)
- JournalEntry (to-one, via JournalEntryDetailRevenueEventItem.JournalEntry)
- JournalRun (to-one, via JournalEntryDetailRevenueEventItem.JournalEntry.JournalRun)

**Referenced by:** none

## JournalEntryDetailTaxationItem

**References (foreign keys / relations):**
- CreditAccountingCode (to-one, type AccountingCode, via JournalEntryDetailTaxationItem.CreditAccountingCode)
- DebitAccountingCode (to-one, type AccountingCode, via JournalEntryDetailTaxationItem.DebitAccountingCode)
- JournalEntry (to-one, via JournalEntryDetailTaxationItem.JournalEntry)
- JournalRun (to-one, via JournalEntryDetailTaxationItem.JournalEntry.JournalRun)

**Referenced by:** none

## JournalEntryDetailUnrealizedFxGainLoss

**References (foreign keys / relations):**
- CreditAccountingCode (to-one, type AccountingCode, via JournalEntryDetailUnrealizedFxGainLoss.CreditAccountingCode)
- DebitAccountingCode (to-one, type AccountingCode, via JournalEntryDetailUnrealizedFxGainLoss.DebitAccountingCode)
- JournalEntry (to-one, via JournalEntryDetailUnrealizedFxGainLoss.JournalEntry)
- JournalRun (to-one, via JournalEntryDetailUnrealizedFxGainLoss.JournalEntry.JournalRun)

**Referenced by:** none

## JournalEntryItem

**References (foreign keys / relations):**
- AccountingCode (to-one, via JournalEntryItem.AccountingCode)
- AccountingPeriod (to-one, via JournalEntryItem.JournalEntry.AccountingPeriod)
- JournalEntry (to-one, via JournalEntryItem.JournalEntry)
- JournalRun (to-one, via JournalEntryItem.JournalEntry.JournalRun)

**Referenced by:** none

## JournalRun

**References:** none

**Referenced by:** none

## NotificationHistoryEmailEvent

**References (foreign keys / relations):**
- Account (to-one, via NotificationHistoryEmailEvent.Account)
- BillToContact (to-one, type Contact, via NotificationHistoryEmailEvent.Account.BillToContact)
- DefaultPaymentMethod (to-one, type PaymentMethod, via NotificationHistoryEmailEvent.Account.DefaultPaymentMethod)
- EmailHistory (to-one, via NotificationHistoryEmailEvent.EmailHistory)
- ParentAccount (to-one, type Account, via NotificationHistoryEmailEvent.Account.ParentAccount)
- ShipToContact (to-one, type Contact, via NotificationHistoryEmailEvent.Account.ShipToContact)
- SoldToContact (to-one, type Contact, via NotificationHistoryEmailEvent.Account.SoldToContact)

**Referenced by:** none

## Order

**References (foreign keys / relations):**
- Account (to-one, via Order.Account)
- BillToContact (to-one, type Contact, via Order.Account.BillToContact)
- DefaultPaymentMethod (to-one, type PaymentMethod, via Order.Account.DefaultPaymentMethod)
- ParentAccount (to-one, type Account, via Order.Account.ParentAccount)
- ShipToContact (to-one, type Contact, via Order.Account.ShipToContact)
- SoldToContact (to-one, type Contact, via Order.Account.SoldToContact)

**Referenced by:** none

## OrderAction

**References (foreign keys / relations):**
- Account (to-one, via OrderAction.Order.Account)
- AddRatePlan (to-one, type RatePlan, via OrderAction.AddRatePlan)
- BillToContact (to-one, type Contact, via OrderAction.Order.Account.BillToContact)
- DefaultPaymentMethod (to-one, type PaymentMethod, via OrderAction.Order.Account.DefaultPaymentMethod)
- Order (to-one, via OrderAction.Order)
- OrderActionBillTo (to-one, type Contact, via OrderAction.OrderActionBillTo)
- OrderActionShipTo (to-one, type Contact, via OrderAction.OrderActionShipTo)
- OrderActionSoldTo (to-one, type Contact, via OrderAction.OrderActionSoldTo)
- ParentAccount (to-one, type Account, via OrderAction.Order.Account.ParentAccount)
- RemoveRatePlan (to-one, type RatePlan, via OrderAction.RemoveRatePlan)
- ShipToContact (to-one, type Contact, via OrderAction.Order.Account.ShipToContact)
- SoldToContact (to-one, type Contact, via OrderAction.Order.Account.SoldToContact)
- Subscription (to-one, via OrderAction.Subscription)
- SubscriptionBillTo (to-one, type Contact, via OrderAction.SubscriptionBillTo)
- SubscriptionBillToSnapshot (to-one, type ContactSnapshot, via OrderAction.SubscriptionBillToSnapshot)
- SubscriptionOwnerAccount (to-one, type Account, via OrderAction.SubscriptionOwnerAccount)
- SubscriptionOwnerAccountBillTo (to-one, type Contact, via OrderAction.SubscriptionOwnerAccountBillTo)
- SubscriptionOwnerAccountShipTo (to-one, type Contact, via OrderAction.SubscriptionOwnerAccountShipTo)
- SubscriptionOwnerAccountSoldTo (to-one, type Contact, via OrderAction.SubscriptionOwnerAccountSoldTo)
- SubscriptionShipTo (to-one, type Contact, via OrderAction.SubscriptionShipTo)
- SubscriptionShipToSnapshot (to-one, type ContactSnapshot, via OrderAction.SubscriptionShipToSnapshot)
- SubscriptionSoldTo (to-one, type Contact, via OrderAction.SubscriptionSoldTo)
- SubscriptionSoldToSnapshot (to-one, type ContactSnapshot, via OrderAction.SubscriptionSoldToSnapshot)
- SubscriptionVersionAmendment (to-one, type Amendment, via OrderAction.SubscriptionVersionAmendment)
- UpdateRatePlan (to-one, type RatePlan, via OrderAction.UpdateRatePlan)

**Referenced by:** none

## OrderLineItem

**References (foreign keys / relations):**
- ProductRatePlanChargeId -> ProductRatePlanCharge (to-one)
- Account (to-one, via OrderLineItem.Order.Account)
- AdjustmentLiabilityAccountingCode (to-one, type AccountingCode, via OrderLineItem.AdjustmentLiabilityAccountingCode)
- AdjustmentRevenueAccountingCode (to-one, type AccountingCode, via OrderLineItem.AdjustmentRevenueAccountingCode)
- BillToContact (to-one, type Contact, via OrderLineItem.Order.Account.BillToContact)
- BillToContactSnapshot (to-one, type ContactSnapshot, via OrderLineItem.BillToContactSnapshot)
- ContractAssetAccountingCode (to-one, type AccountingCode, via OrderLineItem.ContractAssetAccountingCode)
- ContractLiabilityAccountingCode (to-one, type AccountingCode, via OrderLineItem.ContractLiabilityAccountingCode)
- ContractRecognizedRevenueAccountingCode (to-one, type AccountingCode, via OrderLineItem.ContractRecognizedRevenueAccountingCode)
- DefaultPaymentMethod (to-one, type PaymentMethod, via OrderLineItem.Order.Account.DefaultPaymentMethod)
- DeferredRevenueAccountingCode (to-one, type AccountingCode, via OrderLineItem.DeferredRevenueAccountingCode)
- OliBillToContact (to-one, type Contact, via OrderLineItem.OliBillToContact)
- OliShipToContact (to-one, type Contact, via OrderLineItem.OliShipToContact)
- OliSoldToContact (to-one, type Contact, via OrderLineItem.OliSoldToContact)
- Order (to-one, via OrderLineItem.Order)
- OriginalOrder (to-one, type Order, via OrderLineItem.OriginalOrder)
- OriginalOrderLineItem (to-one, type OrderLineItem, via OrderLineItem.OriginalOrderLineItem)
- ParentAccount (to-one, type Account, via OrderLineItem.Order.Account.ParentAccount)
- Product (to-one, via OrderLineItem.ProductRatePlanCharge.ProductRatePlan.Product)
- ProductRatePlan (to-one, via OrderLineItem.ProductRatePlanCharge.ProductRatePlan)
- RecognizedRevenueAccountingCode (to-one, type AccountingCode, via OrderLineItem.RecognizedRevenueAccountingCode)
- ShipToContact (to-one, type Contact, via OrderLineItem.Order.Account.ShipToContact)
- ShipToContactSnapshot (to-one, type ContactSnapshot, via OrderLineItem.ShipToContactSnapshot)
- SoldToContact (to-one, type Contact, via OrderLineItem.Order.Account.SoldToContact)
- SoldToContactSnapshot (to-one, type ContactSnapshot, via OrderLineItem.SoldToContactSnapshot)
- UnbilledReceivablesAccountingCode (to-one, type AccountingCode, via OrderLineItem.UnbilledReceivablesAccountingCode)

**Referenced by:** none

## OrderMrr

**References (foreign keys / relations):**
- Account (to-one, via OrderMrr.OrderAction.Order.Account)
- Amendment (to-one, via OrderMrr.RatePlanCharge.RatePlan.Amendment)
- BillToContact (to-one, type Contact, via OrderMrr.OrderAction.Order.Account.BillToContact)
- DefaultPaymentMethod (to-one, type PaymentMethod, via OrderMrr.OrderAction.Order.Account.DefaultPaymentMethod)
- Order (to-one, via OrderMrr.OrderAction.Order)
- OrderAction (to-one, via OrderMrr.OrderAction)
- ParentAccount (to-one, type Account, via OrderMrr.OrderAction.Order.Account.ParentAccount)
- Product (to-one, via OrderMrr.RatePlanCharge.RatePlan.ProductRatePlan.Product)
- ProductRatePlan (to-one, via OrderMrr.RatePlanCharge.RatePlan.ProductRatePlan)
- ProductRatePlanCharge (to-one, via OrderMrr.RatePlanCharge.ProductRatePlanCharge)
- RatePlan (to-one, via OrderMrr.RatePlanCharge.RatePlan)
- RatePlanCharge (to-one, via OrderMrr.RatePlanCharge)
- ShipToContact (to-one, type Contact, via OrderMrr.OrderAction.Order.Account.ShipToContact)
- SoldToContact (to-one, type Contact, via OrderMrr.OrderAction.Order.Account.SoldToContact)
- Subscription (to-one, via OrderMrr.OrderAction.Subscription)
- SubscriptionBillTo (to-one, type Contact, via OrderMrr.OrderAction.SubscriptionBillTo)
- SubscriptionBillToSnapshot (to-one, type ContactSnapshot, via OrderMrr.OrderAction.SubscriptionBillToSnapshot)
- SubscriptionShipTo (to-one, type Contact, via OrderMrr.OrderAction.SubscriptionShipTo)
- SubscriptionShipToSnapshot (to-one, type ContactSnapshot, via OrderMrr.OrderAction.SubscriptionShipToSnapshot)
- SubscriptionSoldTo (to-one, type Contact, via OrderMrr.OrderAction.SubscriptionSoldTo)
- SubscriptionSoldToSnapshot (to-one, type ContactSnapshot, via OrderMrr.OrderAction.SubscriptionSoldToSnapshot)
- SubscriptionVersionAmendment (to-one, type Amendment, via OrderMrr.OrderAction.SubscriptionVersionAmendment)

**Referenced by:** none

## OrderQuantity

**References (foreign keys / relations):**
- Account (to-one, via OrderQuantity.OrderAction.Order.Account)
- Amendment (to-one, via OrderQuantity.RatePlanCharge.RatePlan.Amendment)
- BillToContact (to-one, type Contact, via OrderQuantity.OrderAction.Order.Account.BillToContact)
- DefaultPaymentMethod (to-one, type PaymentMethod, via OrderQuantity.OrderAction.Order.Account.DefaultPaymentMethod)
- Order (to-one, via OrderQuantity.OrderAction.Order)
- OrderAction (to-one, via OrderQuantity.OrderAction)
- ParentAccount (to-one, type Account, via OrderQuantity.OrderAction.Order.Account.ParentAccount)
- Product (to-one, via OrderQuantity.RatePlanCharge.RatePlan.ProductRatePlan.Product)
- ProductRatePlan (to-one, via OrderQuantity.RatePlanCharge.RatePlan.ProductRatePlan)
- ProductRatePlanCharge (to-one, via OrderQuantity.RatePlanCharge.ProductRatePlanCharge)
- RatePlan (to-one, via OrderQuantity.RatePlanCharge.RatePlan)
- RatePlanCharge (to-one, via OrderQuantity.RatePlanCharge)
- ShipToContact (to-one, type Contact, via OrderQuantity.OrderAction.Order.Account.ShipToContact)
- SoldToContact (to-one, type Contact, via OrderQuantity.OrderAction.Order.Account.SoldToContact)
- Subscription (to-one, via OrderQuantity.OrderAction.Subscription)
- SubscriptionBillTo (to-one, type Contact, via OrderQuantity.OrderAction.SubscriptionBillTo)
- SubscriptionBillToSnapshot (to-one, type ContactSnapshot, via OrderQuantity.OrderAction.SubscriptionBillToSnapshot)
- SubscriptionShipTo (to-one, type Contact, via OrderQuantity.OrderAction.SubscriptionShipTo)
- SubscriptionShipToSnapshot (to-one, type ContactSnapshot, via OrderQuantity.OrderAction.SubscriptionShipToSnapshot)
- SubscriptionSoldTo (to-one, type Contact, via OrderQuantity.OrderAction.SubscriptionSoldTo)
- SubscriptionSoldToSnapshot (to-one, type ContactSnapshot, via OrderQuantity.OrderAction.SubscriptionSoldToSnapshot)
- SubscriptionVersionAmendment (to-one, type Amendment, via OrderQuantity.OrderAction.SubscriptionVersionAmendment)

**Referenced by:** none

## OrderTcb

**References (foreign keys / relations):**
- Account (to-one, via OrderTcb.OrderAction.Order.Account)
- Amendment (to-one, via OrderTcb.RatePlanCharge.RatePlan.Amendment)
- BillToContact (to-one, type Contact, via OrderTcb.OrderAction.Order.Account.BillToContact)
- DefaultPaymentMethod (to-one, type PaymentMethod, via OrderTcb.OrderAction.Order.Account.DefaultPaymentMethod)
- Order (to-one, via OrderTcb.OrderAction.Order)
- OrderAction (to-one, via OrderTcb.OrderAction)
- ParentAccount (to-one, type Account, via OrderTcb.OrderAction.Order.Account.ParentAccount)
- Product (to-one, via OrderTcb.RatePlanCharge.RatePlan.ProductRatePlan.Product)
- ProductRatePlan (to-one, via OrderTcb.RatePlanCharge.RatePlan.ProductRatePlan)
- ProductRatePlanCharge (to-one, via OrderTcb.RatePlanCharge.ProductRatePlanCharge)
- RatePlan (to-one, via OrderTcb.RatePlanCharge.RatePlan)
- RatePlanCharge (to-one, via OrderTcb.RatePlanCharge)
- ShipToContact (to-one, type Contact, via OrderTcb.OrderAction.Order.Account.ShipToContact)
- SoldToContact (to-one, type Contact, via OrderTcb.OrderAction.Order.Account.SoldToContact)
- Subscription (to-one, via OrderTcb.OrderAction.Subscription)
- SubscriptionBillTo (to-one, type Contact, via OrderTcb.OrderAction.SubscriptionBillTo)
- SubscriptionBillToSnapshot (to-one, type ContactSnapshot, via OrderTcb.OrderAction.SubscriptionBillToSnapshot)
- SubscriptionShipTo (to-one, type Contact, via OrderTcb.OrderAction.SubscriptionShipTo)
- SubscriptionShipToSnapshot (to-one, type ContactSnapshot, via OrderTcb.OrderAction.SubscriptionShipToSnapshot)
- SubscriptionSoldTo (to-one, type Contact, via OrderTcb.OrderAction.SubscriptionSoldTo)
- SubscriptionSoldToSnapshot (to-one, type ContactSnapshot, via OrderTcb.OrderAction.SubscriptionSoldToSnapshot)
- SubscriptionVersionAmendment (to-one, type Amendment, via OrderTcb.OrderAction.SubscriptionVersionAmendment)

**Referenced by:** none

## OrderTcv

**References (foreign keys / relations):**
- Account (to-one, via OrderTcv.OrderAction.Order.Account)
- Amendment (to-one, via OrderTcv.RatePlanCharge.RatePlan.Amendment)
- BillToContact (to-one, type Contact, via OrderTcv.OrderAction.Order.Account.BillToContact)
- DefaultPaymentMethod (to-one, type PaymentMethod, via OrderTcv.OrderAction.Order.Account.DefaultPaymentMethod)
- Order (to-one, via OrderTcv.OrderAction.Order)
- OrderAction (to-one, via OrderTcv.OrderAction)
- ParentAccount (to-one, type Account, via OrderTcv.OrderAction.Order.Account.ParentAccount)
- Product (to-one, via OrderTcv.RatePlanCharge.RatePlan.ProductRatePlan.Product)
- ProductRatePlan (to-one, via OrderTcv.RatePlanCharge.RatePlan.ProductRatePlan)
- ProductRatePlanCharge (to-one, via OrderTcv.RatePlanCharge.ProductRatePlanCharge)
- RatePlan (to-one, via OrderTcv.RatePlanCharge.RatePlan)
- RatePlanCharge (to-one, via OrderTcv.RatePlanCharge)
- ShipToContact (to-one, type Contact, via OrderTcv.OrderAction.Order.Account.ShipToContact)
- SoldToContact (to-one, type Contact, via OrderTcv.OrderAction.Order.Account.SoldToContact)
- Subscription (to-one, via OrderTcv.OrderAction.Subscription)
- SubscriptionBillTo (to-one, type Contact, via OrderTcv.OrderAction.SubscriptionBillTo)
- SubscriptionBillToSnapshot (to-one, type ContactSnapshot, via OrderTcv.OrderAction.SubscriptionBillToSnapshot)
- SubscriptionShipTo (to-one, type Contact, via OrderTcv.OrderAction.SubscriptionShipTo)
- SubscriptionShipToSnapshot (to-one, type ContactSnapshot, via OrderTcv.OrderAction.SubscriptionShipToSnapshot)
- SubscriptionSoldTo (to-one, type Contact, via OrderTcv.OrderAction.SubscriptionSoldTo)
- SubscriptionSoldToSnapshot (to-one, type ContactSnapshot, via OrderTcv.OrderAction.SubscriptionSoldToSnapshot)
- SubscriptionVersionAmendment (to-one, type Amendment, via OrderTcv.OrderAction.SubscriptionVersionAmendment)

**Referenced by:** none

## Payment

**References (foreign keys / relations):**
- AccountId -> Account (to-one)
- PaymentMethodId -> PaymentMethod (to-one)
- PaymentMethodSnapshotId -> PaymentMethodSnapshot (to-one)
- BillToContact (to-one, type Contact, via Payment.Account.BillToContact)
- DefaultPaymentMethod (to-one, type PaymentMethod, via Payment.Account.DefaultPaymentMethod)
- ParentAccount (to-one, type Account, via Payment.Account.ParentAccount)
- ShipToContact (to-one, type Contact, via Payment.Account.ShipToContact)
- SoldToContact (to-one, type Contact, via Payment.Account.SoldToContact)

**Referenced by:**
- InvoicePayment.PaymentId
- PaymentTransactionLog.PaymentId

## PaymentApplication

**References (foreign keys / relations):**
- Account (to-one, via PaymentApplication.Account)
- AccountingPeriod (to-one, via PaymentApplication.JournalEntry.AccountingPeriod)
- AccountReceivableAccountingCode (to-one, type AccountingCode, via PaymentApplication.AccountReceivableAccountingCode)
- ApplicationGroup (to-one, via PaymentApplication.ApplicationGroup)
- BillToContact (to-one, type Contact, via PaymentApplication.Account.BillToContact)
- CashAccountingCode (to-one, type AccountingCode, via PaymentApplication.CashAccountingCode)
- DebitMemo (to-one, via PaymentApplication.DebitMemo)
- DefaultPaymentMethod (to-one, type PaymentMethod, via PaymentApplication.Account.DefaultPaymentMethod)
- Invoice (to-one, via PaymentApplication.Invoice)
- JournalEntry (to-one, via PaymentApplication.JournalEntry)
- JournalRun (to-one, via PaymentApplication.JournalEntry.JournalRun)
- ParentAccount (to-one, type Account, via PaymentApplication.Account.ParentAccount)
- Payment (to-one, via PaymentApplication.Payment)
- PaymentMethod (to-one, via PaymentApplication.Payment.PaymentMethod)
- PaymentMethodSnapshot (to-one, via PaymentApplication.Payment.PaymentMethodSnapshot)
- ShipToContact (to-one, type Contact, via PaymentApplication.Account.ShipToContact)
- SoldToContact (to-one, type Contact, via PaymentApplication.Account.SoldToContact)
- UnappliedPaymentAccountingCode (to-one, type AccountingCode, via PaymentApplication.UnappliedPaymentAccountingCode)

**Referenced by:** none

## PaymentApplicationItem

**References (foreign keys / relations):**
- Account (to-one, via PaymentApplicationItem.PaymentApplication.Account)
- AccountingPeriod (to-one, via PaymentApplicationItem.JournalEntry.AccountingPeriod)
- AccountReceivableAccountingCode (to-one, type AccountingCode, via PaymentApplicationItem.AccountReceivableAccountingCode)
- ApplicationGroup (to-one, via PaymentApplicationItem.ApplicationGroup)
- BillToContact (to-one, type Contact, via PaymentApplicationItem.PaymentApplication.Account.BillToContact)
- CashAccountingCode (to-one, type AccountingCode, via PaymentApplicationItem.CashAccountingCode)
- DebitMemo (to-one, via PaymentApplicationItem.PaymentApplication.DebitMemo)
- DebitMemoItem (to-one, via PaymentApplicationItem.DebitMemoItem)
- DebitTaxationItem (to-one, via PaymentApplicationItem.DebitTaxationItem)
- DefaultPaymentMethod (to-one, type PaymentMethod, via PaymentApplicationItem.PaymentApplication.Account.DefaultPaymentMethod)
- Invoice (to-one, via PaymentApplicationItem.PaymentApplication.Invoice)
- InvoiceItem (to-one, via PaymentApplicationItem.InvoiceItem)
- JournalEntry (to-one, via PaymentApplicationItem.JournalEntry)
- JournalRun (to-one, via PaymentApplicationItem.JournalEntry.JournalRun)
- ParentAccount (to-one, type Account, via PaymentApplicationItem.PaymentApplication.Account.ParentAccount)
- Payment (to-one, via PaymentApplicationItem.ApplicationGroup.Payment)
- PaymentApplication (to-one, via PaymentApplicationItem.PaymentApplication)
- PaymentMethod (to-one, via PaymentApplicationItem.ApplicationGroup.Payment.PaymentMethod)
- PaymentMethodSnapshot (to-one, via PaymentApplicationItem.ApplicationGroup.Payment.PaymentMethodSnapshot)
- ShipToContact (to-one, type Contact, via PaymentApplicationItem.PaymentApplication.Account.ShipToContact)
- SoldToContact (to-one, type Contact, via PaymentApplicationItem.PaymentApplication.Account.SoldToContact)
- TaxationItem (to-one, via PaymentApplicationItem.TaxationItem)
- UnappliedPaymentAccountingCode (to-one, type AccountingCode, via PaymentApplicationItem.UnappliedPaymentAccountingCode)

**Referenced by:** none

## PaymentGatewayReconciliationEventLog

**References (foreign keys / relations):**
- PaymentReconciliationJob (to-one, via PaymentGatewayReconciliationEventLog.PaymentReconciliationJob)

**Referenced by:** none

## PaymentMethod

**References (foreign keys / relations):**
- PaymentMethodToken (to-many, via PaymentMethod.PaymentMethodToken)
- StoredCredentialProfile (to-many, via PaymentMethod.StoredCredentialProfile)

**Referenced by:**
- Account.DefaultPaymentMethodId
- Payment.PaymentMethodId
- PaymentMethodTransactionLog.PaymentMethodId

## PaymentMethodPriority

**References:** none

**Referenced by:** none

## PaymentMethodToken

**References (foreign keys / relations):**
- PaymentMethod (to-one, via PaymentMethodToken.PaymentMethod)

**Referenced by:** none

## PaymentMethodTransactionLog

**References (foreign keys / relations):**
- PaymentMethodId -> PaymentMethod (to-one)
- Account (to-one, via PaymentMethodTransactionLog.Account)
- BillToContact (to-one, type Contact, via PaymentMethodTransactionLog.Account.BillToContact)
- DefaultPaymentMethod (to-one, type PaymentMethod, via PaymentMethodTransactionLog.Account.DefaultPaymentMethod)
- ParentAccount (to-one, type Account, via PaymentMethodTransactionLog.Account.ParentAccount)
- ShipToContact (to-one, type Contact, via PaymentMethodTransactionLog.Account.ShipToContact)
- SoldToContact (to-one, type Contact, via PaymentMethodTransactionLog.Account.SoldToContact)

**Referenced by:** none

## PaymentPart

**References (foreign keys / relations):**
- InvoiceId -> Invoice (to-one)
- Account (to-one, via PaymentPart.Account)
- BillToContact (to-one, type Contact, via PaymentPart.Account.BillToContact)
- DebitMemo (to-one, via PaymentPart.DebitMemo)
- DefaultPaymentMethod (to-one, type PaymentMethod, via PaymentPart.Account.DefaultPaymentMethod)
- ParentAccount (to-one, type Account, via PaymentPart.Account.ParentAccount)
- Payment (to-one, via PaymentPart.Payment)
- PaymentMethod (to-one, via PaymentPart.Payment.PaymentMethod)
- PaymentMethodSnapshot (to-one, via PaymentPart.Payment.PaymentMethodSnapshot)
- ShipToContact (to-one, type Contact, via PaymentPart.Account.ShipToContact)
- SoldToContact (to-one, type Contact, via PaymentPart.Account.SoldToContact)

**Referenced by:** none

## PaymentPartItem

**References (foreign keys / relations):**
- Account (to-one, via PaymentPartItem.PaymentPart.Account)
- BillToContact (to-one, type Contact, via PaymentPartItem.PaymentPart.Account.BillToContact)
- DebitMemo (to-one, via PaymentPartItem.PaymentPart.DebitMemo)
- DebitMemoItem (to-one, via PaymentPartItem.DebitMemoItem)
- DebitTaxationItem (to-one, via PaymentPartItem.DebitTaxationItem)
- DefaultPaymentMethod (to-one, type PaymentMethod, via PaymentPartItem.PaymentPart.Account.DefaultPaymentMethod)
- Invoice (to-one, via PaymentPartItem.InvoiceItem.Invoice)
- InvoiceItem (to-one, via PaymentPartItem.InvoiceItem)
- ParentAccount (to-one, type Account, via PaymentPartItem.PaymentPart.Account.ParentAccount)
- Payment (to-one, via PaymentPartItem.PaymentPart.Payment)
- PaymentMethod (to-one, via PaymentPartItem.PaymentPart.Payment.PaymentMethod)
- PaymentMethodSnapshot (to-one, via PaymentPartItem.PaymentPart.Payment.PaymentMethodSnapshot)
- PaymentPart (to-one, via PaymentPartItem.PaymentPart)
- ShipToContact (to-one, type Contact, via PaymentPartItem.PaymentPart.Account.ShipToContact)
- SoldToContact (to-one, type Contact, via PaymentPartItem.PaymentPart.Account.SoldToContact)
- TaxationItem (to-one, via PaymentPartItem.TaxationItem)

**Referenced by:** none

## PaymentReconciliationJob

**References:** none

**Referenced by:** none

## PaymentReconciliationLog

**References (foreign keys / relations):**
- PaymentGatewayReconciliationEventLog (to-one, via PaymentReconciliationLog.PaymentGatewayReconciliationEventLog)
- PaymentReconciliationJob (to-one, via PaymentReconciliationLog.PaymentGatewayReconciliationEventLog.PaymentReconciliationJob)

**Referenced by:** none

## PaymentRun

**References:** none

**Referenced by:** none

## PaymentSchedule

**References (foreign keys / relations):**
- Account (to-one, via PaymentSchedule.Account)
- BillToContact (to-one, type Contact, via PaymentSchedule.Account.BillToContact)
- DebitMemo (to-one, via PaymentSchedule.DebitMemo)
- DefaultPaymentMethod (to-one, type PaymentMethod, via PaymentSchedule.Account.DefaultPaymentMethod)
- Invoice (to-one, via PaymentSchedule.Invoice)
- ParentAccount (to-one, type Account, via PaymentSchedule.Account.ParentAccount)
- ShipToContact (to-one, type Contact, via PaymentSchedule.Account.ShipToContact)
- SoldToContact (to-one, type Contact, via PaymentSchedule.Account.SoldToContact)

**Referenced by:** none

## PaymentScheduleItem

**References (foreign keys / relations):**
- Account (to-one, via PaymentScheduleItem.PaymentSchedule.Account)
- BillToContact (to-one, type Contact, via PaymentScheduleItem.PaymentSchedule.Account.BillToContact)
- DebitMemo (to-one, via PaymentScheduleItem.DebitMemo)
- DefaultPaymentMethod (to-one, type PaymentMethod, via PaymentScheduleItem.PaymentSchedule.Account.DefaultPaymentMethod)
- Invoice (to-one, via PaymentScheduleItem.Invoice)
- ParentAccount (to-one, type Account, via PaymentScheduleItem.PaymentSchedule.Account.ParentAccount)
- Payment (to-one, via PaymentScheduleItem.Payment)
- PaymentMethod (to-one, via PaymentScheduleItem.Payment.PaymentMethod)
- PaymentMethodSnapshot (to-one, via PaymentScheduleItem.Payment.PaymentMethodSnapshot)
- PaymentSchedule (to-one, via PaymentScheduleItem.PaymentSchedule)
- ShipToContact (to-one, type Contact, via PaymentScheduleItem.PaymentSchedule.Account.ShipToContact)
- SoldToContact (to-one, type Contact, via PaymentScheduleItem.PaymentSchedule.Account.SoldToContact)

**Referenced by:** none

## PaymentScheduleItemPayment

**References (foreign keys / relations):**
- Payment (to-one, via PaymentScheduleItemPayment.Payment)
- PaymentMethod (to-one, via PaymentScheduleItemPayment.Payment.PaymentMethod)
- PaymentMethodSnapshot (to-one, via PaymentScheduleItemPayment.Payment.PaymentMethodSnapshot)
- PaymentScheduleItem (to-one, via PaymentScheduleItemPayment.PaymentScheduleItem)

**Referenced by:** none

## PaymentTransactionLog

**References (foreign keys / relations):**
- PaymentId -> Payment (to-one)
- Account (to-one, via PaymentTransactionLog.Account)
- BillToContact (to-one, type Contact, via PaymentTransactionLog.Account.BillToContact)
- DefaultPaymentMethod (to-one, type PaymentMethod, via PaymentTransactionLog.Account.DefaultPaymentMethod)
- ParentAccount (to-one, type Account, via PaymentTransactionLog.Account.ParentAccount)
- PaymentMethod (to-one, via PaymentTransactionLog.Payment.PaymentMethod)
- PaymentMethodSnapshot (to-one, via PaymentTransactionLog.Payment.PaymentMethodSnapshot)
- ShipToContact (to-one, type Contact, via PaymentTransactionLog.Account.ShipToContact)
- SoldToContact (to-one, type Contact, via PaymentTransactionLog.Account.SoldToContact)

**Referenced by:** none

## PrepaidBalance

**References (foreign keys / relations):**
- AccountId -> Account (to-one)
- SubscriptionId -> Subscription (to-one)
- BillToContact (to-one, type Contact, via PrepaidBalance.Account.BillToContact)
- DefaultPaymentMethod (to-one, type PaymentMethod, via PrepaidBalance.Account.DefaultPaymentMethod)
- ParentAccount (to-one, type Account, via PrepaidBalance.Account.ParentAccount)
- ShipToContact (to-one, type Contact, via PrepaidBalance.Account.ShipToContact)
- SoldToContact (to-one, type Contact, via PrepaidBalance.Account.SoldToContact)

**Referenced by:**
- Fund.PrepaidBalanceId
- PrepaidBalanceTransaction.PrepaidBalanceId
- ValidityPeriodSummary.PrepaidBalanceId

## PrepaidBalanceTransaction

**References (foreign keys / relations):**
- AccountId -> Account (to-one)
- PrepaidBalanceId -> PrepaidBalance (to-one)
- Amendment (to-one, via PrepaidBalanceTransaction.Fund.RatePlanCharge.RatePlan.Amendment)
- BillToContact (to-one, type Contact, via PrepaidBalanceTransaction.Fund.Account.BillToContact)
- DefaultPaymentMethod (to-one, type PaymentMethod, via PrepaidBalanceTransaction.Fund.Account.DefaultPaymentMethod)
- Fund (to-one, via PrepaidBalanceTransaction.Fund)
- ParentAccount (to-one, type Account, via PrepaidBalanceTransaction.Fund.Account.ParentAccount)
- Product (to-one, via PrepaidBalanceTransaction.Fund.RatePlanCharge.RatePlan.ProductRatePlan.Product)
- ProductRatePlan (to-one, via PrepaidBalanceTransaction.Fund.RatePlanCharge.RatePlan.ProductRatePlan)
- ProductRatePlanCharge (to-one, via PrepaidBalanceTransaction.Fund.RatePlanCharge.ProductRatePlanCharge)
- RatePlan (to-one, via PrepaidBalanceTransaction.Fund.RatePlanCharge.RatePlan)
- RatePlanCharge (to-one, via PrepaidBalanceTransaction.Fund.RatePlanCharge)
- ShipToContact (to-one, type Contact, via PrepaidBalanceTransaction.Fund.Account.ShipToContact)
- SoldToContact (to-one, type Contact, via PrepaidBalanceTransaction.Fund.Account.SoldToContact)
- Subscription (to-one, via PrepaidBalanceTransaction.Fund.PrepaidBalance.Subscription)
- ValidityPeriodSummary (to-one, via PrepaidBalanceTransaction.Fund.ValidityPeriodSummary)

**Referenced by:** none

## ProcessedUsage

**References (foreign keys / relations):**
- AccountId -> Account (to-one)
- InvoiceItemId -> InvoiceItem (to-one)
- RatePlanChargeId -> RatePlanCharge (to-one)
- SubscriptionId -> Subscription (to-one)
- UsageId -> Usage (to-one)
- Amendment (to-one, via ProcessedUsage.RatePlanCharge.RatePlan.Amendment)
- BillToContact (to-one, type Contact, via ProcessedUsage.Usage.Account.BillToContact)
- CreditMemo (to-one, via ProcessedUsage.CreditMemoItem.CreditMemo)
- CreditMemoItem (to-one, via ProcessedUsage.CreditMemoItem)
- DefaultPaymentMethod (to-one, type PaymentMethod, via ProcessedUsage.Usage.Account.DefaultPaymentMethod)
- Invoice (to-one, via ProcessedUsage.InvoiceItem.Invoice)
- ParentAccount (to-one, type Account, via ProcessedUsage.Usage.Account.ParentAccount)
- Product (to-one, via ProcessedUsage.RatePlanCharge.RatePlan.ProductRatePlan.Product)
- ProductRatePlan (to-one, via ProcessedUsage.RatePlanCharge.RatePlan.ProductRatePlan)
- ProductRatePlanCharge (to-one, via ProcessedUsage.RatePlanCharge.ProductRatePlanCharge)
- RatePlan (to-one, via ProcessedUsage.RatePlanCharge.RatePlan)
- ShipToContact (to-one, type Contact, via ProcessedUsage.Usage.Account.ShipToContact)
- SoldToContact (to-one, type Contact, via ProcessedUsage.Usage.Account.SoldToContact)

**Referenced by:** none

## Product

**References:** none

**Referenced by:**
- InvoiceItem.ProductId
- ProductRatePlan.ProductId

## ProductChargeDefinition

**References (foreign keys / relations):**
- ProductRatePlanCharge (to-one, via ProductChargeDefinition.ProductRatePlanCharge)

**Referenced by:** none

## ProductRatePlan

**References (foreign keys / relations):**
- ProductId -> Product (to-one)

**Referenced by:**
- ProductRatePlanCharge.ProductRatePlanId
- RatePlan.ProductRatePlanId

## ProductRatePlanCharge

**References (foreign keys / relations):**
- DiscountClassId -> DiscountClass (to-one)
- ProductRatePlanId -> ProductRatePlan (to-one)
- AccountReceivableAccountingCode (to-one, type AccountingCode, via ProductRatePlanCharge.AccountReceivableAccountingCode)
- AdjustmentLiabilityAccountingCode (to-one, type AccountingCode, via ProductRatePlanCharge.AdjustmentLiabilityAccountingCode)
- AdjustmentRevenueAccountingCode (to-one, type AccountingCode, via ProductRatePlanCharge.AdjustmentRevenueAccountingCode)
- ContractAssetAccountingCode (to-one, type AccountingCode, via ProductRatePlanCharge.ContractAssetAccountingCode)
- ContractLiabilityAccountingCode (to-one, type AccountingCode, via ProductRatePlanCharge.ContractLiabilityAccountingCode)
- ContractRecognizedRevenueAccountingCode (to-one, type AccountingCode, via ProductRatePlanCharge.ContractRecognizedRevenueAccountingCode)
- DeferredRevenueAccountingCode (to-one, type AccountingCode, via ProductRatePlanCharge.DeferredRevenueAccountingCode)
- Product (to-one, via ProductRatePlanCharge.ProductRatePlan.Product)
- RecognizedRevenueAccountingCode (to-one, type AccountingCode, via ProductRatePlanCharge.RecognizedRevenueAccountingCode)
- UnbilledReceivablesAccountingCode (to-one, type AccountingCode, via ProductRatePlanCharge.UnbilledReceivablesAccountingCode)

**Referenced by:**
- OrderLineItem.ProductRatePlanChargeId
- ProductRatePlanChargeTier.ProductRatePlanChargeId
- RatePlanCharge.ProductRatePlanChargeId

## ProductRatePlanChargeTier

**References (foreign keys / relations):**
- ProductRatePlanChargeId -> ProductRatePlanCharge (to-one)
- Product (to-one, via ProductRatePlanChargeTier.ProductRatePlanCharge.ProductRatePlan.Product)
- ProductChargeDefinition (to-one, via ProductRatePlanChargeTier.ProductChargeDefinition)
- ProductRatePlan (to-one, via ProductRatePlanChargeTier.ProductRatePlanCharge.ProductRatePlan)

**Referenced by:** none

## Ramp

**References (foreign keys / relations):**
- Order (to-one, via Ramp.Order)
- Subscription (to-one, via Ramp.Subscription)

**Referenced by:** none

## RampInterval

**References (foreign keys / relations):**
- Order (to-one, via RampInterval.Ramp.Order)
- Ramp (to-one, via RampInterval.Ramp)
- Subscription (to-one, via RampInterval.Ramp.Subscription)

**Referenced by:** none

## RampIntervalDeltaMetrics

**References (foreign keys / relations):**
- Order (to-one, via RampIntervalDeltaMetrics.RampInterval.Ramp.Order)
- ProductRatePlanCharge (to-one, via RampIntervalDeltaMetrics.ProductRatePlanCharge)
- Ramp (to-one, via RampIntervalDeltaMetrics.RampInterval.Ramp)
- RampInterval (to-one, via RampIntervalDeltaMetrics.RampInterval)
- Subscription (to-one, via RampIntervalDeltaMetrics.RampInterval.Ramp.Subscription)

**Referenced by:** none

## RampIntervalDeltaMrr

**References (foreign keys / relations):**
- Order (to-one, via RampIntervalDeltaMrr.RampIntervalDeltaMetrics.RampInterval.Ramp.Order)
- ProductRatePlanCharge (to-one, via RampIntervalDeltaMrr.RampIntervalDeltaMetrics.ProductRatePlanCharge)
- Ramp (to-one, via RampIntervalDeltaMrr.RampIntervalDeltaMetrics.RampInterval.Ramp)
- RampInterval (to-one, via RampIntervalDeltaMrr.RampIntervalDeltaMetrics.RampInterval)
- RampIntervalDeltaMetrics (to-one, via RampIntervalDeltaMrr.RampIntervalDeltaMetrics)
- Subscription (to-one, via RampIntervalDeltaMrr.RampIntervalDeltaMetrics.RampInterval.Ramp.Subscription)

**Referenced by:** none

## RampIntervalDeltaQuantity

**References (foreign keys / relations):**
- Order (to-one, via RampIntervalDeltaQuantity.RampIntervalDeltaMetrics.RampInterval.Ramp.Order)
- ProductRatePlanCharge (to-one, via RampIntervalDeltaQuantity.RampIntervalDeltaMetrics.ProductRatePlanCharge)
- Ramp (to-one, via RampIntervalDeltaQuantity.RampIntervalDeltaMetrics.RampInterval.Ramp)
- RampInterval (to-one, via RampIntervalDeltaQuantity.RampIntervalDeltaMetrics.RampInterval)
- RampIntervalDeltaMetrics (to-one, via RampIntervalDeltaQuantity.RampIntervalDeltaMetrics)
- Subscription (to-one, via RampIntervalDeltaQuantity.RampIntervalDeltaMetrics.RampInterval.Ramp.Subscription)

**Referenced by:** none

## RampIntervalMetrics

**References (foreign keys / relations):**
- Amendment (to-one, via RampIntervalMetrics.RatePlanCharge.RatePlan.Amendment)
- Order (to-one, via RampIntervalMetrics.RampInterval.Ramp.Order)
- Product (to-one, via RampIntervalMetrics.RatePlanCharge.RatePlan.ProductRatePlan.Product)
- ProductRatePlan (to-one, via RampIntervalMetrics.RatePlanCharge.RatePlan.ProductRatePlan)
- ProductRatePlanCharge (to-one, via RampIntervalMetrics.RatePlanCharge.ProductRatePlanCharge)
- Ramp (to-one, via RampIntervalMetrics.RampInterval.Ramp)
- RampInterval (to-one, via RampIntervalMetrics.RampInterval)
- RatePlan (to-one, via RampIntervalMetrics.RatePlanCharge.RatePlan)
- RatePlanCharge (to-one, via RampIntervalMetrics.RatePlanCharge)
- Subscription (to-one, via RampIntervalMetrics.RampInterval.Ramp.Subscription)

**Referenced by:** none

## RampIntervalMrr

**References (foreign keys / relations):**
- Amendment (to-one, via RampIntervalMrr.RampIntervalMetrics.RatePlanCharge.RatePlan.Amendment)
- Order (to-one, via RampIntervalMrr.RampIntervalMetrics.RampInterval.Ramp.Order)
- Product (to-one, via RampIntervalMrr.RampIntervalMetrics.RatePlanCharge.RatePlan.ProductRatePlan.Product)
- ProductRatePlan (to-one, via RampIntervalMrr.RampIntervalMetrics.RatePlanCharge.RatePlan.ProductRatePlan)
- ProductRatePlanCharge (to-one, via RampIntervalMrr.RampIntervalMetrics.RatePlanCharge.ProductRatePlanCharge)
- Ramp (to-one, via RampIntervalMrr.RampIntervalMetrics.RampInterval.Ramp)
- RampInterval (to-one, via RampIntervalMrr.RampIntervalMetrics.RampInterval)
- RampIntervalMetrics (to-one, via RampIntervalMrr.RampIntervalMetrics)
- RatePlan (to-one, via RampIntervalMrr.RampIntervalMetrics.RatePlanCharge.RatePlan)
- RatePlanCharge (to-one, via RampIntervalMrr.RampIntervalMetrics.RatePlanCharge)
- Subscription (to-one, via RampIntervalMrr.RampIntervalMetrics.RampInterval.Ramp.Subscription)

**Referenced by:** none

## RatePlan

**References (foreign keys / relations):**
- AmendmentId -> Amendment (to-one)
- InvoiceOwnerId -> Account (to-one, as InvoiceOwner)
- ProductRatePlanId -> ProductRatePlan (to-one)
- SubscriptionId -> Subscription (to-one)
- Account (to-one, via RatePlan.Subscription.Account)
- BillToContact (to-one, type Contact, via RatePlan.Subscription.Account.BillToContact)
- DefaultPaymentMethod (to-one, type PaymentMethod, via RatePlan.Subscription.Account.DefaultPaymentMethod)
- ParentAccount (to-one, type Account, via RatePlan.Subscription.Account.ParentAccount)
- Product (to-one, via RatePlan.ProductRatePlan.Product)
- ShipToContact (to-one, type Contact, via RatePlan.Subscription.Account.ShipToContact)
- SoldToContact (to-one, type Contact, via RatePlan.Subscription.Account.SoldToContact)
- SubscriptionVersionAmendment (to-one, type Amendment, via RatePlan.Subscription.SubscriptionVersionAmendment)
- SubscriptionStatusHistory (to-many, via RatePlan.Subscription.SubscriptionStatusHistory)

**Referenced by:**
- RatePlanCharge.RatePlanId

## RatePlanCharge

**References (foreign keys / relations):**
- InvoiceOwnerId -> Account (to-one, as InvoiceOwner)
- ProductRatePlanChargeId -> ProductRatePlanCharge (to-one)
- RatePlanId -> RatePlan (to-one)
- SubscriptionId -> Subscription (to-one)
- Account (to-one, via RatePlanCharge.RatePlan.Subscription.Account)
- AccountReceivableAccountingCode (to-one, type AccountingCode, via RatePlanCharge.AccountReceivableAccountingCode)
- Amendment (to-one, via RatePlanCharge.RatePlan.Amendment)
- BillToContact (to-one, type Contact, via RatePlanCharge.RatePlan.Subscription.Account.BillToContact)
- BillToContactSnapshot (to-one, type ContactSnapshot, via RatePlanCharge.BillToContactSnapshot)
- DefaultPaymentMethod (to-one, type PaymentMethod, via RatePlanCharge.RatePlan.Subscription.Account.DefaultPaymentMethod)
- DeferredRevenueAccountingCode (to-one, type AccountingCode, via RatePlanCharge.DeferredRevenueAccountingCode)
- ParentAccount (to-one, type Account, via RatePlanCharge.RatePlan.Subscription.Account.ParentAccount)
- Product (to-one, via RatePlanCharge.RatePlan.ProductRatePlan.Product)
- ProductRatePlan (to-one, via RatePlanCharge.RatePlan.ProductRatePlan)
- RecognizedRevenueAccountingCode (to-one, type AccountingCode, via RatePlanCharge.RecognizedRevenueAccountingCode)
- ShipToContact (to-one, type Contact, via RatePlanCharge.RatePlan.Subscription.Account.ShipToContact)
- ShipToContactSnapshot (to-one, type ContactSnapshot, via RatePlanCharge.ShipToContactSnapshot)
- SoldToContact (to-one, type Contact, via RatePlanCharge.RatePlan.Subscription.Account.SoldToContact)
- SoldToContactSnapshot (to-one, type ContactSnapshot, via RatePlanCharge.SoldToContactSnapshot)
- SubscriptionBillTo (to-one, type Contact, via RatePlanCharge.RatePlan.Subscription.SubscriptionBillTo)
- SubscriptionBillToSnapshot (to-one, type ContactSnapshot, via RatePlanCharge.RatePlan.Subscription.SubscriptionBillToSnapshot)
- SubscriptionShipTo (to-one, type Contact, via RatePlanCharge.RatePlan.Subscription.SubscriptionShipTo)
- SubscriptionShipToSnapshot (to-one, type ContactSnapshot, via RatePlanCharge.RatePlan.Subscription.SubscriptionShipToSnapshot)
- SubscriptionSoldTo (to-one, type Contact, via RatePlanCharge.RatePlan.Subscription.SubscriptionSoldTo)
- SubscriptionSoldToSnapshot (to-one, type ContactSnapshot, via RatePlanCharge.RatePlan.Subscription.SubscriptionSoldToSnapshot)
- SubscriptionStatusHistory (to-many, via RatePlanCharge.RatePlan.Subscription.SubscriptionStatusHistory)

**Referenced by:**
- BillingPreviewRunResult.RatePlanChargeId
- DailyConsumptionSummary.RatePlanChargeId
- Fund.RatePlanChargeId
- InvoiceItem.RatePlanChargeId
- ProcessedUsage.RatePlanChargeId
- RatePlanChargeTier.RatePlanChargeId
- RatingResult.RatePlanChargeId
- SubscriptionChargeDeliverySchedule.RatePlanChargeId

## RatePlanChargeTier

**References (foreign keys / relations):**
- RatePlanChargeId -> RatePlanCharge (to-one)
- Amendment (to-one, via RatePlanChargeTier.RatePlanCharge.RatePlan.Amendment)
- Product (to-one, via RatePlanChargeTier.RatePlanCharge.RatePlan.ProductRatePlan.Product)
- ProductRatePlan (to-one, via RatePlanChargeTier.RatePlanCharge.RatePlan.ProductRatePlan)
- ProductRatePlanCharge (to-one, via RatePlanChargeTier.RatePlanCharge.ProductRatePlanCharge)
- RatePlan (to-one, via RatePlanChargeTier.RatePlanCharge.RatePlan)
- Subscription (to-one, via RatePlanChargeTier.RatePlanCharge.RatePlan.Subscription)
- SubscriptionStatusHistory (to-many, via RatePlanChargeTier.RatePlanCharge.RatePlan.Subscription.SubscriptionStatusHistory)

**Referenced by:** none

## RatingResult

**References (foreign keys / relations):**
- AccountId -> Account (to-one)
- RatePlanChargeId -> RatePlanCharge (to-one)
- SubscriptionId -> Subscription (to-one)
- Amendment (to-one, via RatingResult.RatePlanCharge.RatePlan.Amendment)
- BillToContact (to-one, type Contact, via RatingResult.Account.BillToContact)
- DefaultPaymentMethod (to-one, type PaymentMethod, via RatingResult.Account.DefaultPaymentMethod)
- Invoice (to-one, via RatingResult.InvoiceItem.Invoice)
- InvoiceItem (to-one, via RatingResult.InvoiceItem)
- ParentAccount (to-one, type Account, via RatingResult.Account.ParentAccount)
- Product (to-one, via RatingResult.RatePlanCharge.RatePlan.ProductRatePlan.Product)
- ProductRatePlan (to-one, via RatingResult.RatePlanCharge.RatePlan.ProductRatePlan)
- ProductRatePlanCharge (to-one, via RatingResult.RatePlanCharge.ProductRatePlanCharge)
- RatePlan (to-one, via RatingResult.RatePlanCharge.RatePlan)
- ShipToContact (to-one, type Contact, via RatingResult.Account.ShipToContact)
- SoldToContact (to-one, type Contact, via RatingResult.Account.SoldToContact)

**Referenced by:** none

## Refund

**References (foreign keys / relations):**
- AccountId -> Account (to-one)
- PaymentMethodSnapshotId -> PaymentMethodSnapshot (to-one)
- BillToContact (to-one, type Contact, via Refund.Account.BillToContact)
- DefaultPaymentMethod (to-one, type PaymentMethod, via Refund.Account.DefaultPaymentMethod)
- ParentAccount (to-one, type Account, via Refund.Account.ParentAccount)
- ShipToContact (to-one, type Contact, via Refund.Account.ShipToContact)
- SoldToContact (to-one, type Contact, via Refund.Account.SoldToContact)

**Referenced by:**
- RefundInvoicePayment.RefundId
- RefundTransactionLog.RefundId

## RefundApplication

**References (foreign keys / relations):**
- Account (to-one, via RefundApplication.Account)
- AccountingPeriod (to-one, via RefundApplication.JournalEntry.AccountingPeriod)
- AccountReceivableAccountingCode (to-one, type AccountingCode, via RefundApplication.AccountReceivableAccountingCode)
- ApplicationGroup (to-one, via RefundApplication.ApplicationGroup)
- BillToContact (to-one, type Contact, via RefundApplication.Account.BillToContact)
- CashAccountingCode (to-one, type AccountingCode, via RefundApplication.CashAccountingCode)
- CreditMemo (to-one, via RefundApplication.CreditMemo)
- DefaultPaymentMethod (to-one, type PaymentMethod, via RefundApplication.Account.DefaultPaymentMethod)
- JournalEntry (to-one, via RefundApplication.JournalEntry)
- JournalRun (to-one, via RefundApplication.JournalEntry.JournalRun)
- OnAccountAccountingCode (to-one, type AccountingCode, via RefundApplication.OnAccountAccountingCode)
- ParentAccount (to-one, type Account, via RefundApplication.Account.ParentAccount)
- Payment (to-one, via RefundApplication.Payment)
- PaymentMethod (to-one, via RefundApplication.Payment.PaymentMethod)
- PaymentMethodSnapshot (to-one, via RefundApplication.Payment.PaymentMethodSnapshot)
- Refund (to-one, via RefundApplication.Refund)
- ShipToContact (to-one, type Contact, via RefundApplication.Account.ShipToContact)
- SoldToContact (to-one, type Contact, via RefundApplication.Account.SoldToContact)
- UnappliedPaymentAccountingCode (to-one, type AccountingCode, via RefundApplication.UnappliedPaymentAccountingCode)

**Referenced by:** none

## RefundApplicationItem

**References (foreign keys / relations):**
- Account (to-one, via RefundApplicationItem.RefundApplication.Account)
- AccountingPeriod (to-one, via RefundApplicationItem.JournalEntry.AccountingPeriod)
- AccountReceivableAccountingCode (to-one, type AccountingCode, via RefundApplicationItem.AccountReceivableAccountingCode)
- ApplicationGroup (to-one, via RefundApplicationItem.ApplicationGroup)
- BillToContact (to-one, type Contact, via RefundApplicationItem.RefundApplication.Account.BillToContact)
- CashAccountingCode (to-one, type AccountingCode, via RefundApplicationItem.CashAccountingCode)
- CreditMemo (to-one, via RefundApplicationItem.RefundApplication.CreditMemo)
- CreditMemoItem (to-one, via RefundApplicationItem.CreditMemoItem)
- CreditTaxationItem (to-one, via RefundApplicationItem.CreditTaxationItem)
- DefaultPaymentMethod (to-one, type PaymentMethod, via RefundApplicationItem.RefundApplication.Account.DefaultPaymentMethod)
- JournalEntry (to-one, via RefundApplicationItem.JournalEntry)
- JournalRun (to-one, via RefundApplicationItem.JournalEntry.JournalRun)
- OnAccountAccountingCode (to-one, type AccountingCode, via RefundApplicationItem.OnAccountAccountingCode)
- ParentAccount (to-one, type Account, via RefundApplicationItem.RefundApplication.Account.ParentAccount)
- Payment (to-one, via RefundApplicationItem.RefundApplication.Payment)
- PaymentMethod (to-one, via RefundApplicationItem.RefundApplication.Payment.PaymentMethod)
- PaymentMethodSnapshot (to-one, via RefundApplicationItem.RefundApplication.Payment.PaymentMethodSnapshot)
- Refund (to-one, via RefundApplicationItem.RefundApplication.Refund)
- RefundApplication (to-one, via RefundApplicationItem.RefundApplication)
- ShipToContact (to-one, type Contact, via RefundApplicationItem.RefundApplication.Account.ShipToContact)
- SoldToContact (to-one, type Contact, via RefundApplicationItem.RefundApplication.Account.SoldToContact)
- UnappliedPaymentAccountingCode (to-one, type AccountingCode, via RefundApplicationItem.UnappliedPaymentAccountingCode)

**Referenced by:** none

## RefundInvoicePayment

**References (foreign keys / relations):**
- InvoiceId -> Invoice (to-one)
- InvoicePaymentId -> InvoicePayment (to-one)
- RefundId -> Refund (to-one)
- Account (to-one, via RefundInvoicePayment.Refund.Account)
- AccountingPeriod (to-one, via RefundInvoicePayment.JournalEntry.AccountingPeriod)
- AccountReceivableAccountingCode (to-one, type AccountingCode, via RefundInvoicePayment.AccountReceivableAccountingCode)
- BillToContact (to-one, type Contact, via RefundInvoicePayment.Refund.Account.BillToContact)
- CashAccountingCode (to-one, type AccountingCode, via RefundInvoicePayment.CashAccountingCode)
- DefaultPaymentMethod (to-one, type PaymentMethod, via RefundInvoicePayment.Refund.Account.DefaultPaymentMethod)
- JournalEntry (to-one, via RefundInvoicePayment.JournalEntry)
- JournalRun (to-one, via RefundInvoicePayment.JournalEntry.JournalRun)
- ParentAccount (to-one, type Account, via RefundInvoicePayment.Refund.Account.ParentAccount)
- Payment (to-one, via RefundInvoicePayment.InvoicePayment.Payment)
- PaymentMethod (to-one, via RefundInvoicePayment.InvoicePayment.Payment.PaymentMethod)
- PaymentMethodSnapshot (to-one, via RefundInvoicePayment.Refund.PaymentMethodSnapshot)
- ShipToContact (to-one, type Contact, via RefundInvoicePayment.Refund.Account.ShipToContact)
- SoldToContact (to-one, type Contact, via RefundInvoicePayment.Refund.Account.SoldToContact)

**Referenced by:** none

## RefundPart

**References (foreign keys / relations):**
- Account (to-one, via RefundPart.Account)
- BillToContact (to-one, type Contact, via RefundPart.Account.BillToContact)
- CreditMemo (to-one, via RefundPart.CreditMemo)
- DefaultPaymentMethod (to-one, type PaymentMethod, via RefundPart.Account.DefaultPaymentMethod)
- ParentAccount (to-one, type Account, via RefundPart.Account.ParentAccount)
- Payment (to-one, via RefundPart.Payment)
- PaymentMethod (to-one, via RefundPart.Payment.PaymentMethod)
- PaymentMethodSnapshot (to-one, via RefundPart.Payment.PaymentMethodSnapshot)
- Refund (to-one, via RefundPart.Refund)
- ShipToContact (to-one, type Contact, via RefundPart.Account.ShipToContact)
- SoldToContact (to-one, type Contact, via RefundPart.Account.SoldToContact)

**Referenced by:** none

## RefundPartItem

**References (foreign keys / relations):**
- Account (to-one, via RefundPartItem.RefundPart.Account)
- BillToContact (to-one, type Contact, via RefundPartItem.RefundPart.Account.BillToContact)
- CreditMemo (to-one, via RefundPartItem.RefundPart.CreditMemo)
- CreditMemoItem (to-one, via RefundPartItem.CreditMemoItem)
- DefaultPaymentMethod (to-one, type PaymentMethod, via RefundPartItem.RefundPart.Account.DefaultPaymentMethod)
- ParentAccount (to-one, type Account, via RefundPartItem.RefundPart.Account.ParentAccount)
- Payment (to-one, via RefundPartItem.RefundPart.Payment)
- PaymentMethod (to-one, via RefundPartItem.RefundPart.Payment.PaymentMethod)
- PaymentMethodSnapshot (to-one, via RefundPartItem.RefundPart.Payment.PaymentMethodSnapshot)
- Refund (to-one, via RefundPartItem.RefundPart.Refund)
- RefundPart (to-one, via RefundPartItem.RefundPart)
- ShipToContact (to-one, type Contact, via RefundPartItem.RefundPart.Account.ShipToContact)
- SoldToContact (to-one, type Contact, via RefundPartItem.RefundPart.Account.SoldToContact)

**Referenced by:** none

## RefundTransactionLog

**References (foreign keys / relations):**
- RefundId -> Refund (to-one)
- PaymentMethodSnapshot (to-one, via RefundTransactionLog.Refund.PaymentMethodSnapshot)

**Referenced by:** none

## RevenueRecognitionEventsTransaction

**References:** none

**Referenced by:** none

## SmartPreventionAudit

**References:** none

**Referenced by:** none

## StoredCredentialProfile

**References (foreign keys / relations):**
- PaymentMethod (to-one, via StoredCredentialProfile.PaymentMethod)
- GatewayProfileData (to-many, via StoredCredentialProfile.GatewayProfileData)

**Referenced by:** none

## Subscription

**References (foreign keys / relations):**
- AccountId -> Account (to-one)
- InvoiceOwnerId -> Account (to-one, as InvoiceOwner)
- SubscriptionBillToId -> Contact (to-one, as SubscriptionBillTo)
- SubscriptionBillToSnapshotId -> ContactSnapshot (to-one, as SubscriptionBillToSnapshot)
- SubscriptionShipToId -> Contact (to-one, as SubscriptionShipTo)
- SubscriptionShipToSnapshotId -> ContactSnapshot (to-one, as SubscriptionShipToSnapshot)
- SubscriptionSoldToId -> Contact (to-one, as SubscriptionSoldTo)
- SubscriptionSoldToSnapshotId -> ContactSnapshot (to-one, as SubscriptionSoldToSnapshot)
- BillToContact (to-one, type Contact, via Subscription.Account.BillToContact)
- DefaultPaymentMethod (to-one, type PaymentMethod, via Subscription.Account.DefaultPaymentMethod)
- ParentAccount (to-one, type Account, via Subscription.Account.ParentAccount)
- ShipToContact (to-one, type Contact, via Subscription.Account.ShipToContact)
- SoldToContact (to-one, type Contact, via Subscription.Account.SoldToContact)
- SubscriptionVersionAmendment (to-one, type Amendment, via Subscription.SubscriptionVersionAmendment)
- SubscriptionStatusHistory (to-many, via Subscription.SubscriptionStatusHistory)

**Referenced by:**
- BillingPreviewRunResult.SubscriptionId
- DeliveryAdjustment.SubscriptionId
- InvoiceItem.SubscriptionId
- PrepaidBalance.SubscriptionId
- ProcessedUsage.SubscriptionId
- RatePlan.SubscriptionId
- RatePlanCharge.SubscriptionId
- RatingResult.SubscriptionId
- Usage.SubscriptionId

## SubscriptionChargeDeliverySchedule

**References (foreign keys / relations):**
- RatePlanChargeId -> RatePlanCharge (to-one)
- Account (to-one, via SubscriptionChargeDeliverySchedule.RatePlanCharge.RatePlan.Subscription.Account)
- Amendment (to-one, via SubscriptionChargeDeliverySchedule.RatePlanCharge.RatePlan.Amendment)
- BillToContact (to-one, type Contact, via SubscriptionChargeDeliverySchedule.RatePlanCharge.RatePlan.Subscription.Account.BillToContact)
- DefaultPaymentMethod (to-one, type PaymentMethod, via SubscriptionChargeDeliverySchedule.RatePlanCharge.RatePlan.Subscription.Account.DefaultPaymentMethod)
- InvoiceOwner (to-one, type Account, via SubscriptionChargeDeliverySchedule.RatePlanCharge.RatePlan.Subscription.InvoiceOwner)
- ParentAccount (to-one, type Account, via SubscriptionChargeDeliverySchedule.RatePlanCharge.RatePlan.Subscription.Account.ParentAccount)
- Product (to-one, via SubscriptionChargeDeliverySchedule.RatePlanCharge.RatePlan.ProductRatePlan.Product)
- ProductRatePlan (to-one, via SubscriptionChargeDeliverySchedule.RatePlanCharge.RatePlan.ProductRatePlan)
- ProductRatePlanCharge (to-one, via SubscriptionChargeDeliverySchedule.RatePlanCharge.ProductRatePlanCharge)
- RatePlan (to-one, via SubscriptionChargeDeliverySchedule.RatePlanCharge.RatePlan)
- ShipToContact (to-one, type Contact, via SubscriptionChargeDeliverySchedule.RatePlanCharge.RatePlan.Subscription.Account.ShipToContact)
- SoldToContact (to-one, type Contact, via SubscriptionChargeDeliverySchedule.RatePlanCharge.RatePlan.Subscription.Account.SoldToContact)
- Subscription (to-one, via SubscriptionChargeDeliverySchedule.RatePlanCharge.RatePlan.Subscription)

**Referenced by:** none

## SubscriptionStatusHistory

**References:** none

**Referenced by:** none

## TaxationItem

**References (foreign keys / relations):**
- InvoiceId -> Invoice (to-one)
- InvoiceItemId -> InvoiceItem (to-one)
- Account (to-one, via TaxationItem.InvoiceItem.Invoice.Account)
- AccountingPeriod (to-one, via TaxationItem.JournalEntry.AccountingPeriod)
- AccountReceivableAccountingCode (to-one, type AccountingCode, via TaxationItem.AccountReceivableAccountingCode)
- Amendment (to-one, via TaxationItem.InvoiceItem.RatePlanCharge.RatePlan.Amendment)
- BillToContact (to-one, type Contact, via TaxationItem.InvoiceItem.Invoice.Account.BillToContact)
- DefaultPaymentMethod (to-one, type PaymentMethod, via TaxationItem.InvoiceItem.Invoice.Account.DefaultPaymentMethod)
- JournalEntry (to-one, via TaxationItem.JournalEntry)
- JournalRun (to-one, via TaxationItem.JournalEntry.JournalRun)
- OrderLineItem (to-one, via TaxationItem.InvoiceItem.OrderLineItem)
- ParentAccount (to-one, type Account, via TaxationItem.InvoiceItem.Invoice.Account.ParentAccount)
- Product (to-one, via TaxationItem.InvoiceItem.ProductRatePlanCharge.ProductRatePlan.Product)
- ProductRatePlan (to-one, via TaxationItem.InvoiceItem.ProductRatePlanCharge.ProductRatePlan)
- ProductRatePlanCharge (to-one, via TaxationItem.InvoiceItem.ProductRatePlanCharge)
- RatePlan (to-one, via TaxationItem.InvoiceItem.RatePlanCharge.RatePlan)
- RatePlanCharge (to-one, via TaxationItem.InvoiceItem.RatePlanCharge)
- SalesTaxPayableAccountingCode (to-one, type AccountingCode, via TaxationItem.SalesTaxPayableAccountingCode)
- ShipToContact (to-one, type Contact, via TaxationItem.InvoiceItem.Invoice.Account.ShipToContact)
- SoldToContact (to-one, type Contact, via TaxationItem.InvoiceItem.Invoice.Account.SoldToContact)
- Subscription (to-one, via TaxationItem.InvoiceItem.RatePlanCharge.RatePlan.Subscription)

**Referenced by:** none

## UpdaterBatch

**References:** none

**Referenced by:** none

## UpdaterDetail

**References (foreign keys / relations):**
- NewPaymentMethod (to-one, type PaymentMethod, via UpdaterDetail.NewPaymentMethod)
- PaymentMethod (to-one, via UpdaterDetail.PaymentMethod)
- UpdaterBatch (to-one, via UpdaterDetail.UpdaterBatch)

**Referenced by:** none

## Usage

**References (foreign keys / relations):**
- AccountId -> Account (to-one)
- SubscriptionId -> Subscription (to-one)
- Amendment (to-one, via Usage.RatePlanCharge.RatePlan.Amendment)
- BillToContact (to-one, type Contact, via Usage.Account.BillToContact)
- DefaultPaymentMethod (to-one, type PaymentMethod, via Usage.Account.DefaultPaymentMethod)
- ParentAccount (to-one, type Account, via Usage.Account.ParentAccount)
- Product (to-one, via Usage.RatePlanCharge.RatePlan.ProductRatePlan.Product)
- ProductRatePlan (to-one, via Usage.RatePlanCharge.RatePlan.ProductRatePlan)
- ProductRatePlanCharge (to-one, via Usage.RatePlanCharge.ProductRatePlanCharge)
- RatePlan (to-one, via Usage.RatePlanCharge.RatePlan)
- RatePlanCharge (to-one, via Usage.RatePlanCharge)
- ShipToContact (to-one, type Contact, via Usage.Account.ShipToContact)
- SoldToContact (to-one, type Contact, via Usage.Account.SoldToContact)

**Referenced by:**
- ProcessedUsage.UsageId

## ValidityPeriodSummary

**References (foreign keys / relations):**
- AccountId -> Account (to-one)
- PrepaidBalanceId -> PrepaidBalance (to-one)
- BillToContact (to-one, type Contact, via ValidityPeriodSummary.Account.BillToContact)
- DefaultPaymentMethod (to-one, type PaymentMethod, via ValidityPeriodSummary.Account.DefaultPaymentMethod)
- ParentAccount (to-one, type Account, via ValidityPeriodSummary.Account.ParentAccount)
- ShipToContact (to-one, type Contact, via ValidityPeriodSummary.Account.ShipToContact)
- SoldToContact (to-one, type Contact, via ValidityPeriodSummary.Account.SoldToContact)
- Subscription (to-one, via ValidityPeriodSummary.PrepaidBalance.Subscription)

**Referenced by:**
- Fund.ValidityPeriodSummaryId
