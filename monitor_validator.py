import yaml
import json
from typing import Dict, List, Tuple, Optional
from pathlib import Path
import re
from urllib.parse import urlparse

class MonitorValidator:
    """
    Validador estricto para monitores de Elastic Synthetics
    """
    
    def __init__(self):
        self.valid_types = ['http', 'tcp', 'icmp', 'browser']
        self.valid_methods = ['GET', 'POST', 'PUT', 'DELETE', 'HEAD', 'OPTIONS', 'PATCH']
        self.valid_locations = [
            'us_central', 'us_east', 'us_west', 'europe_west', 'asia_pacific',
            'south_america', 'africa', 'australia_southeast'
        ]
    
    def validate_monitor_config(self, config: Dict, monitor_type: str) -> Tuple[bool, List[str]]:
        """
        Valida la configuración de un monitor
        """
        errors = []
        
        # Validaciones básicas
        errors.extend(self._validate_basic_fields(config))
        errors.extend(self._validate_schedule(config.get('schedule')))
        errors.extend(self._validate_timeout(config.get('timeout')))
        errors.extend(self._validate_locations(config.get('locations', [])))
        
        # Validaciones específicas por tipo
        if monitor_type == 'http':
            errors.extend(self._validate_http_monitor(config))
        elif monitor_type == 'tcp':
            errors.extend(self._validate_tcp_monitor(config))
        elif monitor_type == 'icmp':
            errors.extend(self._validate_icmp_monitor(config))
        elif monitor_type == 'browser':
            errors.extend(self._validate_browser_monitor(config))
        
        return len(errors) == 0, errors
    
    def _validate_basic_fields(self, config: Dict) -> List[str]:
        """
        Valida campos básicos obligatorios
        """
        errors = []
        
        required_fields = ['name', 'id', 'type', 'enabled', 'schedule', 'timeout', 'locations']
        for field in required_fields:
            if field not in config:
                errors.append(f"Campo obligatorio faltante: {field}")
        
        # Validar tipo
        if config.get('type') not in self.valid_types:
            errors.append(f"Tipo de monitor inválido: {config.get('type')}. Tipos válidos: {self.valid_types}")
        
        # Validar nombre
        if config.get('name') and len(config['name']) < 3:
            errors.append("El nombre debe tener al menos 3 caracteres")
        
        # Validar ID
        if config.get('id') and not re.match(r'^[a-zA-Z0-9_-]+$', config['id']):
            errors.append("El ID solo puede contener letras, números, guiones y guiones bajos")
        
        # Validar enabled
        if 'enabled' in config and not isinstance(config['enabled'], bool):
            errors.append("El campo 'enabled' debe ser booleano")
        
        return errors
    
    def _validate_schedule(self, schedule: Optional[str]) -> List[str]:
        """
        Valida formato de schedule
        """
        errors = []
        
        if not schedule:
            errors.append("Schedule es obligatorio")
            return errors
        
        # Formato: @every 5m, @every 30s, @every 1h
        if not re.match(r'^@every\s+\d+[smh]$', schedule):
            errors.append(f"Formato de schedule inválido: {schedule}. Formato correcto: @every 5m")
        
        # Validar intervalos mínimos
        if 's' in schedule:
            seconds = int(re.search(r'(\d+)s', schedule).group(1))
            if seconds < 10:
                errors.append("El intervalo mínimo es 10 segundos")
        
        return errors
    
    def _validate_timeout(self, timeout: Optional[str]) -> List[str]:
        """
        Valida formato de timeout
        """
        errors = []
        
        if not timeout:
            errors.append("Timeout es obligatorio")
            return errors
        
        if not re.match(r'^\d+[smh]$', timeout):
            errors.append(f"Formato de timeout inválido: {timeout}. Formato correcto: 30s")
        
        # Validar límites
        if 's' in timeout:
            seconds = int(re.search(r'(\d+)s', timeout).group(1))
            if seconds < 1 or seconds > 180:
                errors.append("Timeout debe estar entre 1s y 180s")
        elif 'm' in timeout:
            minutes = int(re.search(r'(\d+)m', timeout).group(1))
            if minutes < 1 or minutes > 3:
                errors.append("Timeout debe estar entre 1m y 3m")
        
        return errors
    
    def _validate_locations(self, locations: List[str]) -> List[str]:
        """
        Valida ubicaciones
        """
        errors = []
        
        if not locations:
            errors.append("Se requiere al menos una ubicación")
            return errors
        
        if not isinstance(locations, list):
            errors.append("Locations debe ser una lista")
            return errors
        
        for location in locations:
            if location not in self.valid_locations:
                errors.append(f"Ubicación inválida: {location}")
        
        return errors
    
    def _validate_http_monitor(self, config: Dict) -> List[str]:
        """
        Valida configuración específica de monitor HTTP
        """
        errors = []
        
        # URLs obligatorias
        if 'urls' not in config:
            errors.append("Monitor HTTP requiere campo 'urls'")
        elif not isinstance(config['urls'], list) or len(config['urls']) == 0:
            errors.append("Monitor HTTP requiere al menos una URL")
        else:
            for url in config['urls']:
                if not self._is_valid_url(url):
                    errors.append(f"URL inválida: {url}")
        
        # Método HTTP
        if 'method' in config:
            if config['method'].upper() not in self.valid_methods:
                errors.append(f"Método HTTP inválido: {config['method']}")
        
        # Max redirects
        if 'max_redirects' in config:
            if not isinstance(config['max_redirects'], int) or config['max_redirects'] < 0:
                errors.append("max_redirects debe ser un entero positivo")
        
        # Headers
        if 'headers' in config:
            if not isinstance(config['headers'], dict):
                errors.append("Headers debe ser un diccionario")
        
        # Status codes
        if 'check.response.status' in config:
            status_codes = config['check.response.status']
            if not isinstance(status_codes, list):
                errors.append("check.response.status debe ser una lista")
            else:
                for code in status_codes:
                    if not isinstance(code, int) or code < 100 or code > 599:
                        errors.append(f"Código de estado inválido: {code}")
        
        return errors
    
    def _validate_tcp_monitor(self, config: Dict) -> List[str]:
        """
        Valida configuración específica de monitor TCP
        """
        errors = []
        
        if 'hosts' not in config:
            errors.append("Monitor TCP requiere campo 'hosts'")
        elif not isinstance(config['hosts'], list) or len(config['hosts']) == 0:
            errors.append("Monitor TCP requiere al menos un host")
        else:
            for host in config['hosts']:
                if not self._is_valid_host_port(host):
                    errors.append(f"Host:puerto inválido: {host}")
        
        return errors
    
    def _validate_icmp_monitor(self, config: Dict) -> List[str]:
        """
        Valida configuración específica de monitor ICMP
        """
        errors = []
        
        if 'hosts' not in config:
            errors.append("Monitor ICMP requiere campo 'hosts'")
        elif not isinstance(config['hosts'], list) or len(config['hosts']) == 0:
            errors.append("Monitor ICMP requiere al menos un host")
        else:
            for host in config['hosts']:
                if not self._is_valid_host(host):
                    errors.append(f"Host inválido: {host}")
        
        if 'wait' in config:
            if not re.match(r'^\d+[smh]$', config['wait']):
                errors.append(f"Formato de wait inválido: {config['wait']}")
        
        return errors
    
    def _validate_browser_monitor(self, config: Dict) -> List[str]:
        """
        Valida configuración específica de monitor Browser
        """
        errors = []
        
        if 'source' not in config:
            errors.append("Monitor Browser requiere campo 'source'")
        elif 'inline' not in config['source']:
            errors.append("Monitor Browser requiere source.inline")
        elif 'script' not in config['source']['inline']:
            errors.append("Monitor Browser requiere source.inline.script")
        
        # Validar script básico
        if 'source' in config and 'inline' in config['source']:
            script = config['source']['inline'].get('script', '')
            if 'journey' not in script:
                errors.append("Script de Browser debe contener función 'journey'")
            if '@elastic/synthetics' not in script:
                errors.append("Script de Browser debe importar '@elastic/synthetics'")
        
        return errors
    
    def _is_valid_url(self, url: str) -> bool:
        """
        Valida formato de URL
        """
        try:
            result = urlparse(url)
            return all([result.scheme, result.netloc]) and result.scheme in ['http', 'https']
        except:
            return False
    
    def _is_valid_host_port(self, host_port: str) -> bool:
        """
        Valida formato host:puerto
        """
        pattern = r'^[a-zA-Z0-9.-]+:\d+$'
        return re.match(pattern, host_port) is not None
    
    def _is_valid_host(self, host: str) -> bool:
        """
        Valida formato de host
        """
        # Hostname o IP
        hostname_pattern = r'^[a-zA-Z0-9.-]+$'
        ip_pattern = r'^(\d{1,3}\.){3}\d{1,3}$'
        return re.match(hostname_pattern, host) or re.match(ip_pattern, host)
    
    def validate_browser_script(self, script: str) -> Tuple[bool, List[str]]:
        """
        Valida script de browser para sintaxis básica
        """
        errors = []
        
        # Validaciones básicas
        if not script.strip():
            errors.append("Script no puede estar vacío")
            return False, errors
        
        # Debe tener imports
        if '@elastic/synthetics' not in script:
            errors.append("Script debe importar @elastic/synthetics")
        
        # Debe tener función journey
        if 'journey(' not in script:
            errors.append("Script debe contener función journey")
        
        # Debe tener steps
        if 'step(' not in script:
            errors.append("Script debe contener al menos un step")
        
        # Validar sintaxis básica de TypeScript
        if script.count('{') != script.count('}'):
            errors.append("Llaves no balanceadas en el script")
        
        if script.count('(') != script.count(')'):
            errors.append("Paréntesis no balanceados en el script")
        
        return len(errors) == 0, errors