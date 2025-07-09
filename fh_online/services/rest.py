import frappe

@frappe.whitelist(allow_guest=True, methods=["GET"])
def get_all_products():
    try:
        products = frappe.db.get_all(
            "Item",
            filters={"disabled": 0},
            fields=[
                "name AS product_id",
                "item_name AS product_name",
                "description AS product_description",
                "item_group AS product_category",
                "product_image"
            ]
        )

        for product in products:
            price = frappe.db.get_value(
                "Item Price",
                {
                    "item_code": product["product_id"],
                    "selling": 1
                },
                "price_list_rate"
            )
            product["selling_price"] = price or 0.0

        return {"status": 200, "products": products}

    except Exception as e:
        frappe.log_error(frappe.get_traceback(), f"{e}")
        return {"error": str(e)}, 400


@frappe.whitelist(allow_guest=True, methods=["GET"])
def get_default_currency():
    try:
        default_currency = frappe.get_single('Global Defaults')
        return {
            'status': 200,
            'message': 'Currency returned successfully.',
            'currency': default_currency.default_currency
        }
    except Exception as e:
        frappe.log_error(frappe.get_traceback(), f"{e}")
        return {'error': str(e)}, 400