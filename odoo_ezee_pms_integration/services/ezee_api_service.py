import requests
import json
import xml.etree.ElementTree as ET
from datetime import datetime
import logging

_logger = logging.getLogger(__name__)

class eZeeAPIService:
    def __init__(self, credentials):
        self.creds = credentials
        self.base_url_login = "https://live.ipms247.com/index.php/page/service.quickbook"
        self.base_url_api = "https://live.ipms247.com/index.php/page/service.PMSAccountAPI"

    def login(self):
        """Returns tuple (success: bool, message: str)"""
        xml_request = f"""<FAS_Interface_Request>
<Request_Type>FAS_Login_User</Request_Type>
<Authentication>
<UserName>{self.creds.username}</UserName>
<UserPassword>{self.creds.password}</UserPassword>
<HotelCode>{self.creds.hotel_code}</HotelCode>
</Authentication>
</FAS_Interface_Request>"""
        
        try:
            response = requests.post(self.base_url_login, data=xml_request, headers={'Content-Type': 'application/xml'})
            if response.status_code == 200:
                root = ET.fromstring(response.content)
                success = root.find('Success')
                if success:
                    self.creds.write({
                        'auth_code': success.find('HotelAuthentication').text,
                        'working_date': success.find('HotelWorkingDate').text,
                        'currency_code': success.find('HotelCurrencyCode').text,
                    })
                    return True, "Login successful"
                else:
                    error = root.find('Errors')
                    msg = error.find('ErrorMessage').text if error is not None else "Unknown Login Error"
                    _logger.error(f"eZee Login Failed: {msg}")
                    return False, msg
            else:
                msg = f"HTTP Error {response.status_code}: {response.text}"
                _logger.error(f"eZee Login Failed: {msg}")
                return False, msg
        except Exception as e:
            msg = f"Connection Exception: {str(e)}"
            _logger.error(f"eZee Login Exception: {str(e)}")
            return False, msg

    def fetch_data(self, api_type, from_date=None, to_date=None):
        request_for_map = {
            'sales': 'XERO_GET_TRANSACTION_DATA',
            'receipt': 'XERO_GET_RECEIPT_DATA',
            'payment': 'XERO_GET_PAYMENT_DATA',
            'journal': 'XERO_GENERAL_JOURNAL_INFO',
            'incidental': 'XERO_INCIDENTAL_INVOICE',
            'config': 'XERO_GET_CONFIG_DATA',
        }
        
        payload = {
            "auth_code": self.creds.auth_code,
            "hotel_code": self.creds.hotel_code,
            "requestfor": request_for_map.get(api_type)
        }

        if from_date:
            from_date_str = from_date.strftime('%Y-%m-%d') if hasattr(from_date, 'strftime') else str(from_date)
            payload["fromdate"] = from_date_str
        if to_date:
            to_date_str = to_date.strftime('%Y-%m-%d') if hasattr(to_date, 'strftime') else str(to_date)
            payload["todate"] = to_date_str
        
        if api_type == 'sales':
            payload["ischeckout"] = "false"

        try:
            response = requests.post(self.base_url_api, json=payload)
            # Log the sync
            self.creds.env['pms.sync.log'].create({
                'hotel_id': self.creds.id,
                'api_type': api_type,
                'sync_date': from_date,
                'status': 'success' if response.status_code == 200 else 'failed',
                'request_payload': json.dumps(payload),
                'response_payload': response.text,
            })
            
            if response.status_code == 200:
                return response.json()
        except Exception as e:
            _logger.error(f"eZee Fetch Data Exception: {str(e)}")
            return None
