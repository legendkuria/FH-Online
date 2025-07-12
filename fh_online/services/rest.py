import frappe
import requests
import random

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


@frappe.whitelist(allow_guest=True, methods="POST")
def customer_registration(**kwargs):
    try:
        mobile_no = kwargs.get('mobile_number')
        email_id = kwargs.get('email_address')
        customer_name = kwargs.get('full_name')

        if not (mobile_no and email_id and customer_name):
            return {"status": 400, "message": "Mobile number, email, and full name are required."}

        customer_exists = frappe.db.exists("Customer", {"mobile_no": mobile_no}) or \
                          frappe.db.exists("Customer", {"email_id": email_id})

        if not customer_exists:
            frappe.enqueue(
                customer_registration_queue,
                queue="default",
                mobile_no=mobile_no,
                email_id=email_id,
                customer_name=customer_name
            )
        else:
            return {"status": 500, "message": "You are already registered."}
        return {"status": 200, "message": "Customer registered Successfully."}

    except Exception as e:
        frappe.log_error(frappe.get_traceback(), "Customer Registration Error")
        return {"status": 500, "error": str(e)}


def customer_registration_queue(mobile_no, email_id, customer_name):
    try:
        customer_doc = frappe.get_doc({
            "doctype": "Customer",
            "mobile_no": mobile_no,
            "email_id": email_id,
            "customer_name": customer_name
        })
        customer_doc.insert(ignore_permissions=True)
        frappe.db.commit()

        if customer_doc.name:
            create_user(email_id, mobile_no, customer_name)

    except Exception as e:
        frappe.log_error(frappe.get_traceback(), "Customer Registration Queue Error")


@frappe.whitelist()
def create_user(email_id, mobile_no, customer_name):
    try:
        name_parts = customer_name.strip().split()
        first_name = name_parts[0]
        middle_name = name_parts[1] if len(name_parts) > 2 else ""
        last_name = name_parts[-1] if len(name_parts) > 1 else ""

        password = str(random.randint(1000, 9999))

        user_doc = frappe.get_doc({
            "doctype": "User",
            "email": email_id,
            "mobile_no": mobile_no,
            "first_name": first_name,
            "middle_name": middle_name,
            "last_name": last_name,
            "new_password": password,
            "role_profile_name": "Customer"
        })
        user_doc.insert(ignore_permissions=True)
        frappe.db.commit()

        if user_doc.name:
            login_identifier = email_id if email_id else mobile_no
            message = (
                f"Hello {first_name}, your account has been created.\n"
                f"Username: {login_identifier}\n"
                f"Password: {password}"
            )
            send_sms(user_doc.mobile_no, message)

    except Exception as e:
        frappe.log_error(frappe.get_traceback(), "User Creation Error")


@frappe.whitelist()
def send_sms(mobile, message):
    api_key = '6bf53f0bda4924760fb1b2e018e2960d'
    partnerID = "9546"
    sender_id = 'LEGEND SOFT'
    endpoint_url = "https://sms.textsms.co.ke/api/services/sendsms/"

    payload = {
        "apikey": api_key,
        "partnerID": partnerID,
        "message": message,
        "shortcode": sender_id,
        "mobile": format_mobile_number(mobile)
    }

    try:
        response = requests.post(endpoint_url, json=payload)
        response = response.json()
        return response
    
    except Exception as e:
        frappe.log_error(frappe.get_traceback(), f"{e}")
        return {'error': str(e)}, 400


def format_mobile_number(mobile):
    try:
        if mobile.isdigit() and len(mobile) >= 9:
            return "254" + mobile[-9:]
        else:
            return "Invalid mobile number."
    except Exception as e:
        frappe.log_error(frappe.get_traceback(), f"{e}")
        return {'error': str(e)}, 400
    

@frappe.whitelist( allow_guest= True, methods="POST" )
def generate_otp(mobile_number):
    mobile_number = mobile_number.lstrip("+")
    try:
        if frappe.db.exists("User", {"mobile_no": mobile_number}):

            existing_otp = frappe.db.get_value("One Time Password", {"mobile_number": mobile_number}, "name")
            if existing_otp:
                frappe.delete_doc("One Time Password", existing_otp)
                frappe.db.commit()
            if send_opt(mobile_number):
                return {
                    'status': 200,
                    'message': f'OTP sent to {mobile_number}.',
                }
        else:
            return {
                'status': 400,
                'message': 'Mobile number not found. Please try again.',
            }
    except Exception as e:
        frappe.log_error(frappe.get_traceback(), f"{str(e)}")
        return {
            'status': 500,
            'message': f'An error occurred: {str(e)}',
        }


def send_opt(mobile_number):
    try:
        frappe.set_user("Administrator")
        otp = random.randint(100000, 999999)
        one_time_password_doc = frappe.get_doc({
            "doctype": "One Time Password",
            "mobile_number": mobile_number,
            "one_time_password": otp
        })
        one_time_password_doc.insert()
        frappe.db.commit()

        message = (
                f"Your OTP is {one_time_password_doc.one_time_password}."
            )
        
        if send_sms(mobile_number, message):
            return "OTP sent successfully."
   
    except Exception as e:
        frappe.log_error(frappe.get_traceback(), f"{str(e)}")
        return {
            'status': 500,
            'message': f'An error occurred: {str(e)}',
        }


@frappe.whitelist(allow_guest= True, methods="GET")
def validate_otp_exists(**kwargs):
    try:
        mobile_number = kwargs.get('mobile_number')
        otp = kwargs.get('otp')
        mobile_number = mobile_number.lstrip("+")
        if frappe.db.exists("One Time Password", {"mobile_number": mobile_number, "one_time_password": otp}):
            return {'status': 200, 'message': 1}
        else:
            return {'status': 200, 'message': 0}
    except Exception as e:
        frappe.log_error(frappe.get_traceback(), f"Error in validate_otp_exists {str(e)}")
        return False


@frappe.whitelist(allow_guest=True, methods="POST")
def password_recovery(usr, new_password):
    try:
        if not usr or not new_password:
            return {'error': 'Missing required parameters: usr and new_password'}, 400

        if "@" in usr and "." in usr:
            user = frappe.get_doc("User", {"email": usr})
        else:
            user = frappe.get_doc("User", {"mobile_no": usr})

        if not user:
            return {'error': 'User not found'}, 404
      
        frappe.utils.password.update_password(user.name, new_password)
        return {'status': 200, 'message': 'Password successfully recovered.'}

    except frappe.DoesNotExistError:
        return {'error': 'User does not exist'}, 404
    except Exception as e:
        frappe.log_error(frappe.get_traceback(), f"Password Recovery Error: {str(e)}")
        return {'error': str(e)}, 500


@frappe.whitelist( allow_guest=True )
def login(usr, pwd):
    try:
        try:
            login_manager = frappe.auth.LoginManager()
            login_manager.authenticate(user=usr, pwd=pwd)
            login_manager.post_login()
        except frappe.exceptions.AuthenticationError:
            frappe.clear_messages()
            frappe.local.response["message"] = {
                "success_key":0,
                "message":"Authentication Error!"
            }

            return

        api_generate = generate_keys(frappe.session.user)
        user = frappe.get_doc('User', frappe.session.user)

        frappe.response["message"] = {
            "success_key":1,
            "message":"Authentication success",
            "sid":frappe.session.sid,
            "api_key":user.api_key,
            "api_secret":api_generate,
            "username":user.username,
            "email":user.email,
            "base_url": frappe.utils.get_url()
        }
    
    except Exception as e:
        frappe.log_error(frappe.get_traceback(), f"Error in login: {e}")
        return {"status": "error", "message": str(e)}

def generate_keys(user):
    try:
        user_details = frappe.get_doc('User', user)
        api_secret = frappe.generate_hash(length=15)

        if not user_details.api_key:
            api_key = frappe.generate_hash(length=15)
            user_details.api_key = api_key

        user_details.api_secret = api_secret
        user_details.save()

        return api_secret
    
    except Exception as e:
        frappe.log_error(frappe.get_traceback(), f"Error in login: {e}")
        return {"status": "error", "message": str(e)}