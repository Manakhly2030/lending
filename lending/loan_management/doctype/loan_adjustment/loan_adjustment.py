# Copyright (c) 2023, Frappe Technologies Pvt. Ltd. and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document
from frappe.utils import cint, flt

from lending.loan_management.doctype.loan_repayment.loan_repayment import calculate_amounts
from lending.loan_management.doctype.loan_restructure.loan_restructure import create_loan_repayment


class LoanAdjustment(Document):
	def validate(self):
		amounts = calculate_amounts(self.loan, self.posting_date)
		precision = cint(frappe.db.get_default("currency_precision")) or 2

		net_payable_amount = (
			flt(amounts.get("unaccrued_interest"), precision)
			+ flt(amounts.get("interest_amount"), precision)
			+ flt(amounts.get("penalty_amount"), precision)
			+ flt(amounts.get("total_charges_payable"), precision)
			- flt(amounts.get("available_security_deposit"), precision)
			+ flt(amounts.get("unbooked_interest"), precision)
			+ flt(amounts.get("unbooked_penalty"), precision)
			+ flt(amounts.get("pending_principal_amount", 0), precision)
		)

		total_paid_amount = 0
		for repayment in self.get("adjustments"):
			if repayment.loan_repayment_type != "Security Deposit Adjustment":
				total_paid_amount += repayment.amount

		if abs(total_paid_amount - net_payable_amount) <= 1:
			repayment_types = [repayment.loan_repayment_type for repayment in self.get("adjustments")]
			if "Security Deposit Adjustment" not in repayment_types:
				self.append(
					"adjustments",
					{
						"loan_repayment_type": "Security Deposit Adjustment",
						"amount": amounts.get("available_security_deposit", 0),
					},
				)

	def on_submit(self):
		for repayment in self.get("adjustments"):
			if repayment.amount:
				create_loan_repayment(
					self.loan,
					self.posting_date,
					repayment.loan_repayment_type,
					repayment.amount,
					self.name,
					payment_account=self.payment_account,
				)
