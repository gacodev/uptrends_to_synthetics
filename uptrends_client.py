import requests
from typing import Dict, List, Optional
from dataclasses import dataclass
from enum import Enum
from dotenv import load_dotenv

load_dotenv()

class MonitorType(Enum):
    HTTP = "Http"
    HTTPS = "Https"
    PING = "Ping"
    DNS = "Dns"
    SMTP = "Smtp"
    POP3 = "Pop3"
    IMAP = "Imap"
    FTP = "Ftp"
    TRANSACTION = "Transaction"
    MULTI_STEP_API = "MultiStepApi"
    SFTP = "Sftp"
    TCP = "Tcp"
    UDP = "Udp"

@dataclass
class UptrendsMonitor:
    monitor_guid: str
    name: str
    url: str
    monitor_type: MonitorType
    check_interval: int
    selected_checkpoints: Dict
    is_active: bool
    http_method: Optional[str] = None
    request_headers: Optional[List[Dict]] = None
    request_body: Optional[str] = None
    expected_http_status_code: Optional[int] = None
    user_agent: Optional[str] = None
    load_time_limit1: Optional[int] = None
    load_time_limit2: Optional[int] = None
    authentication_type: Optional[str] = None
    username: Optional[str] = None
    password: Optional[str] = None
    self_service_transaction_script: Optional[str] = None
    multi_step_api_transaction_script: Optional[str] = None
    msa_steps: Optional[List[Dict]] = None
    transaction_step_definition: Optional[Dict] = None
    browser_type: Optional[str] = None
    browser_window_dimensions: Optional[Dict] = None
    dns_server: Optional[str] = None
    dns_query: Optional[str] = None
    dns_expected_result: Optional[str] = None
    port: Optional[int] = None
    notes: Optional[str] = None
    generate_alert: Optional[bool] = None
    monitor_mode: Optional[str] = None

class UptrendsClient:
    def __init__(self, username: str, password: str):
        self.username = username
        self.password = password
        self.base_url = "https://api.uptrends.com/v4"
        self.session = requests.Session()
        self.session.auth = (username, password)
        self.session.headers.update({
            'Content-Type': 'application/json'
        })
        self.monitor_limit = 4  # Límite inicial para pruebas
    
    def get_monitors_list(self, name_pattern: Optional[str] = None) -> List[Dict]:
        """
        Obtiene lista básica de monitores (ID + Nombre) para filtrado
        """
        url = f"{self.base_url}/Monitor"
        
        try:
            response = self.session.get(url)
            response.raise_for_status()
            
            monitors_data = response.json()
            filtered_monitors = []
            
            for monitor_data in monitors_data:
                monitor_name = monitor_data.get('Name', '')
                monitor_guid = monitor_data.get('MonitorGuid', '')
                
                # Filtrar por patrón si se especifica
                if name_pattern and name_pattern.lower() not in monitor_name.lower():
                    continue
                
                filtered_monitors.append({
                    'guid': monitor_guid,
                    'name': monitor_name,
                    'type': monitor_data.get('MonitorType', 'Unknown'),
                    'is_active': monitor_data.get('IsActive', True)
                })
                
                # Limitar a 5 monitores para pruebas iniciales
                if len(filtered_monitors) >= self.monitor_limit:
                    print(f"Limitando a {self.monitor_limit} monitores para pruebas iniciales")
                    break
            
            return filtered_monitors
            
        except requests.exceptions.RequestException as e:
            print(f"Error al obtener lista de monitores: {e}")
            return []
    
    def get_monitor_details(self, monitor_guid: str) -> Optional[UptrendsMonitor]:
        """
        Obtiene detalles completos de un monitor específico
        """
        url = f"{self.base_url}/Monitor/{monitor_guid}"
        
        try:
            response = self.session.get(url)
            response.raise_for_status()
            
            monitor_data = response.json()
            return self._parse_monitor(monitor_data)
            
        except requests.exceptions.RequestException as e:
            print(f"Error al obtener detalles del monitor {monitor_guid}: {e}")
            return None
    
    def _parse_monitor(self, monitor_data: Dict) -> Optional[UptrendsMonitor]:
        """
        Parsea los datos de un monitor desde la API de Uptrends
        """
        try:
            monitor_type_str = monitor_data.get('MonitorType', 'Http')
            monitor_type = MonitorType(monitor_type_str)
            
            return UptrendsMonitor(
                monitor_guid=monitor_data.get('MonitorGuid', ''),
                name=monitor_data.get('Name', ''),
                url=monitor_data.get('Url', ''),
                monitor_type=monitor_type,
                check_interval=monitor_data.get('CheckInterval', 300),
                selected_checkpoints=monitor_data.get('SelectedCheckpoints', {}),
                is_active=monitor_data.get('IsActive', True),
                http_method=monitor_data.get('HttpMethod'),
                request_headers=monitor_data.get('RequestHeaders'),
                request_body=monitor_data.get('RequestBody'),
                expected_http_status_code=monitor_data.get('ExpectedHttpStatusCode') if monitor_data.get('ExpectedHttpStatusCodeSpecified') else None,
                user_agent=monitor_data.get('UserAgent'),
                load_time_limit1=monitor_data.get('LoadTimeLimit1'),
                load_time_limit2=monitor_data.get('LoadTimeLimit2'),
                authentication_type=monitor_data.get('AuthenticationType'),
                username=monitor_data.get('Username'),
                password=monitor_data.get('Password'),
                self_service_transaction_script=monitor_data.get('SelfServiceTransactionScript'),
                multi_step_api_transaction_script=monitor_data.get('MultiStepApiTransactionScript'),
                msa_steps=monitor_data.get('MsaSteps'),
                transaction_step_definition=monitor_data.get('TransactionStepDefinition'),
                browser_type=monitor_data.get('BrowserType'),
                browser_window_dimensions=monitor_data.get('BrowserWindowDimensions'),
                dns_server=monitor_data.get('DnsServer'),
                dns_query=monitor_data.get('DnsQuery'),
                dns_expected_result=monitor_data.get('DnsExpectedResult'),
                port=monitor_data.get('Port'),
                notes=monitor_data.get('Notes'),
                generate_alert=monitor_data.get('GenerateAlert'),
                monitor_mode=monitor_data.get('MonitorMode')
            )
            
        except (KeyError, ValueError) as e:
            print(f"Error al parsear monitor: {e}")
            return None

