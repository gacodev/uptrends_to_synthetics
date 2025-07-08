import requests
import json
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass
from enum import Enum
import os
from dotenv import load_dotenv
from tenacity import retry, stop_after_attempt, wait_exponential

load_dotenv()

class ElasticMonitorType(Enum):
    HTTP = "http"
    TCP = "tcp"
    ICMP = "icmp"
    BROWSER = "browser"

@dataclass
class MonitorClassification:
    elastic_type: ElasticMonitorType
    confidence: float
    reasoning: str
    recommended_config: Dict

class AIMonitorClassifier:
    def __init__(self, ollama_host: str = "http://localhost:11434", model_name: str = "qwen2.5-coder:7b"):
        self.ollama_host = ollama_host
        self.model_name = model_name
        self.use_hybrid_logic = True
        # Headers para requests
        self.headers = {
            'Content-Type': 'application/json',
            'Accept': 'application/json'
        }
        self.classification_prompt = """
        You are an expert in synthetic monitoring. Your task is to analyze an Uptrends monitor and determine:
        1. The most appropriate monitor type for Elastic Synthetics (http, tcp, icmp, browser)
        2. The ideal configuration for the monitor
        3. Strict validations to ensure it works correctly

        Available monitor types in Elastic Synthetics:
        - http: For simple HTTP/HTTPS monitoring with response validations
        - tcp: For verifying TCP connectivity to a specific port
        - icmp: For basic ping connectivity checks
        - browser: For complex tests that require a real browser

        Decision criteria:
        - If the original monitor is simple HTTP/HTTPS without complex interactions → http
        - If the original monitor is Transaction/MultiStepApi with multiple steps → browser
        - If the original monitor is Ping → icmp
        - If the original monitor verifies specific ports → tcp
        - If the original monitor has transaction scripts → browser

        Respond ONLY with valid JSON in this format:
        {
            "elastic_type": "http|tcp|icmp|browser",
            "confidence": 0.0-1.0,
            "reasoning": "detailed explanation of the decision",
            "recommended_config": {
                "schedule": "@every 5m",
                "timeout": "30s",
                "max_redirects": 3,
                "locations": ["us_central", "us_east"],
                "additional_config": {}
            }
        }
        """
    
    def classify_monitor(self, monitor_data: Dict) -> MonitorClassification:
        """
        Clasifica un monitor usando lógica híbrida:
        - Reglas determinísticas para casos simples (lightweight)
        - IA para casos complejos (browser y edge cases)
        """
        
        if self.use_hybrid_logic:
            # Paso 1: Intentar clasificación con reglas
            rule_result = self._classify_with_rules(monitor_data)
            
            if rule_result:
                return rule_result
            
            # Paso 2: Si las reglas no son suficientes, usar IA
            return self._classify_with_ai(monitor_data)
        else:
            # Modo legacy: usar solo IA
            return self._classify_with_ai(monitor_data)
    
    def _classify_with_rules(self, monitor_data: Dict) -> Optional[MonitorClassification]:
        """
        Clasificación determinística para casos claros
        """
        monitor_type = monitor_data.get('monitor_type', '').lower()
        
        # Verificar si tiene características complejas
        has_complex_features = any([
            monitor_data.get('self_service_transaction_script'),
            monitor_data.get('multi_step_api_transaction_script'),
            monitor_data.get('msa_steps'),
            monitor_data.get('transaction_step_definition'),
            monitor_data.get('browser_type'),
            monitor_type in ['transaction', 'multistepapi']
        ])
        
        # Si tiene características complejas, usar IA
        if has_complex_features:
            return None
        
        # Regla 1: HTTP/HTTPS simple
        if monitor_type in ['http', 'https']:
            return MonitorClassification(
                elastic_type=ElasticMonitorType.HTTP,
                confidence=0.95,
                reasoning=f"RULE: Simple {monitor_type.upper()} monitor without complex features",
                recommended_config=self._get_http_config(monitor_data)
            )
        
        # Regla 2: Ping/ICMP
        elif monitor_type == 'ping':
            return MonitorClassification(
                elastic_type=ElasticMonitorType.ICMP,
                confidence=0.98,
                reasoning="RULE: Ping monitor maps directly to ICMP",
                recommended_config=self._get_icmp_config(monitor_data)
            )
        
        # Regla 3: TCP directo
        elif monitor_type == 'tcp':
            return MonitorClassification(
                elastic_type=ElasticMonitorType.TCP,
                confidence=0.95,
                reasoning="RULE: TCP monitor maps directly",
                recommended_config=self._get_tcp_config(monitor_data)
            )
        
        # Regla 4: DNS como ICMP
        elif monitor_type == 'dns':
            return MonitorClassification(
                elastic_type=ElasticMonitorType.ICMP,
                confidence=0.85,
                reasoning="RULE: DNS monitor can be verified with ICMP",
                recommended_config=self._get_icmp_config(monitor_data)
            )
        
        # Regla 5: Protocolos de email como TCP
        elif monitor_type in ['smtp', 'pop3', 'imap', 'sftp']:
            return MonitorClassification(
                elastic_type=ElasticMonitorType.TCP,
                confidence=0.90,
                reasoning=f"RULE: {monitor_type.upper()} monitor is verified with TCP",
                recommended_config=self._get_tcp_config(monitor_data)
            )
        
        # Si no se puede clasificar con reglas, retornar None para usar IA
        return None
    
    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=4, max=10))
    def _classify_with_ai(self, monitor_data: Dict) -> MonitorClassification:
        """
        Usar IA para casos complejos
        """
        
        monitor_info = f"""
        Uptrends Monitor:
        - Name: {monitor_data.get('name', 'N/A')}
        - Type: {monitor_data.get('monitor_type', 'N/A')}
        - URL: {monitor_data.get('url', 'N/A')}
        - HTTP Method: {monitor_data.get('http_method', 'N/A')}
        - Check Interval: {monitor_data.get('check_interval', 'N/A')} seconds
        - Request Headers: {monitor_data.get('request_headers', 'N/A')}
        - Request Body: {monitor_data.get('request_body', 'N/A')}
        - Expected HTTP Status Code: {monitor_data.get('expected_http_status_code', 'N/A')}
        - Authentication Type: {monitor_data.get('authentication_type', 'N/A')}
        - Transaction Script: {monitor_data.get('self_service_transaction_script', 'N/A')}
        - MultiStep API Script: {monitor_data.get('multi_step_api_transaction_script', 'N/A')}
        - MSA Steps: {monitor_data.get('msa_steps', 'N/A')}
        - Transaction Step Definition: {monitor_data.get('transaction_step_definition', 'N/A')}
        - Browser Type: {monitor_data.get('browser_type', 'N/A')}
        - Port: {monitor_data.get('port', 'N/A')}
        - Notes: {monitor_data.get('notes', 'N/A')}
        """
        
        try:
            # Llamada a Ollama
            response = requests.post(
                f"{self.ollama_host}/api/generate",
                json={
                    "model": self.model_name,
                    "prompt": f"{self.classification_prompt}\n\n{monitor_info}",
                    "stream": False,
                    "options": {
                        "temperature": 0.1,
                        "top_p": 0.9,
                        "num_predict": 1000
                    }
                },
                headers=self.headers,
                timeout=30
            )
            
            if response.status_code != 200:
                print(f"Error en Ollama: {response.status_code}")
                return self._rule_based_classification(monitor_data)
            
            result_text = response.json()["response"]
            
            # Extraer JSON de la respuesta
            json_start = result_text.find('{')
            json_end = result_text.rfind('}') + 1
            
            if json_start == -1 or json_end == 0:
                print("No se encontró JSON válido en la respuesta")
                return self._rule_based_classification(monitor_data)
            
            json_str = result_text[json_start:json_end]
            result = json.loads(json_str)
            
            return MonitorClassification(
                elastic_type=ElasticMonitorType(result['elastic_type']),
                confidence=result['confidence'],
                reasoning=f"AI: {result['reasoning']}",
                recommended_config=result['recommended_config']
            )
            
        except (json.JSONDecodeError, KeyError, ValueError, requests.RequestException) as e:
            print(f"Error al procesar respuesta de IA: {e}")
            # Fallback a clasificación basada en reglas
            return self._rule_based_classification(monitor_data)
    
    def _rule_based_classification(self, monitor_data: Dict) -> MonitorClassification:
        """
        Clasificación basada en reglas como fallback
        """
        monitor_type = monitor_data.get('monitor_type', '').lower()
        
        if monitor_type in ['transaction', 'multistepapi']:
            return MonitorClassification(
                elastic_type=ElasticMonitorType.BROWSER,
                confidence=0.9,
                reasoning="Transaction monitor requires browser",
                recommended_config={
                    "schedule": "@every 5m",
                    "timeout": "60s",
                    "locations": ["us_central"]
                }
            )
        elif monitor_type == 'ping':
            return MonitorClassification(
                elastic_type=ElasticMonitorType.ICMP,
                confidence=0.95,
                reasoning="Ping monitor uses ICMP",
                recommended_config={
                    "schedule": "@every 1m",
                    "timeout": "10s",
                    "locations": ["us_central"]
                }
            )
        elif monitor_type in ['http', 'https']:
            return MonitorClassification(
                elastic_type=ElasticMonitorType.HTTP,
                confidence=0.8,
                reasoning="Simple HTTP monitor",
                recommended_config={
                    "schedule": "@every 3m",
                    "timeout": "30s",
                    "max_redirects": 3,
                    "locations": ["us_central"]
                }
            )
        else:
            return MonitorClassification(
                elastic_type=ElasticMonitorType.HTTP,
                confidence=0.5,
                reasoning="Unknown type, using HTTP as default",
                recommended_config={
                    "schedule": "@every 5m",
                    "timeout": "30s",
                    "locations": ["us_central"]
                }
            )
    
    def validate_classification(self, classification: MonitorClassification) -> Tuple[bool, List[str]]:
        """
        Valida que la clasificación sea correcta y completa
        """
        errors = []
        
        # Validaciones básicas
        if classification.confidence < 0.7:
            errors.append("Very low confidence in classification")
        
        config = classification.recommended_config
        
        # Configuration validations
        if 'schedule' not in config:
            errors.append("Missing schedule configuration")
        
        if 'timeout' not in config:
            errors.append("Missing timeout configuration")
        
        if 'locations' not in config or not config['locations']:
            errors.append("Missing locations configuration")
        
        # Type-specific validations
        if classification.elastic_type == ElasticMonitorType.HTTP:
            if 'max_redirects' not in config:
                errors.append("HTTP monitor must have max_redirects configured")
        
        return len(errors) == 0, errors
    
    def _get_http_config(self, monitor_data: Dict) -> Dict:
        """
        Configuración para monitores HTTP lightweight
        """
        return {
            "schedule": self._get_schedule_from_interval(monitor_data.get('check_interval', 300)),
            "timeout": "30s",
            "locations": ["us_central"],
            "max_redirects": 3,
            "mode": "any"
        }
    
    def _get_icmp_config(self, monitor_data: Dict) -> Dict:
        """
        Configuración para monitores ICMP
        """
        return {
            "schedule": self._get_schedule_from_interval(monitor_data.get('check_interval', 300)),
            "timeout": "10s",
            "locations": ["us_central"],
            "wait": "1s"
        }
    
    def _get_tcp_config(self, monitor_data: Dict) -> Dict:
        """
        Configuración para monitores TCP
        """
        return {
            "schedule": self._get_schedule_from_interval(monitor_data.get('check_interval', 300)),
            "timeout": "30s",
            "locations": ["us_central"]
        }
    
    def _get_schedule_from_interval(self, interval_seconds: int) -> str:
        """
        Convierte intervalo en segundos a formato de schedule de Elastic
        """
        if interval_seconds <= 60:
            return "@every 1m"
        elif interval_seconds <= 180:
            return "@every 3m"
        elif interval_seconds <= 300:
            return "@every 5m"
        elif interval_seconds <= 600:
            return "@every 10m"
        elif interval_seconds <= 900:
            return "@every 15m"
        elif interval_seconds <= 1800:
            return "@every 30m"
        elif interval_seconds <= 3600:
            return "@every 1h"
        else:
            return "@every 5m"  # Default fallback

