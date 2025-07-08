#!/usr/bin/env python3

import os
import json
import click
from typing import List, Dict, Optional
from datetime import datetime
from pathlib import Path

from uptrends_client import UptrendsClient, UptrendsMonitor
from ai_monitor_classifier import AIMonitorClassifier, MonitorClassification
from monitor_validator import MonitorValidator
from dotenv import load_dotenv

load_dotenv()

class MigrationScript:
    def __init__(self, uptrends_client: UptrendsClient, ai_classifier: AIMonitorClassifier):
        self.uptrends_client = uptrends_client
        self.ai_classifier = ai_classifier
        self.monitor_validator = MonitorValidator()
        self.base_output_dir = Path("../nodejs-monitors/monitors")
        self.lightweight_dir = self.base_output_dir / "lightweight"
        self.journey_dir = self.base_output_dir / "journey"
        
        # Crear directorios por tipo
        self.lightweight_dir.mkdir(exist_ok=True, parents=True)
        self.journey_dir.mkdir(exist_ok=True, parents=True)
        
    def migrate_monitors(self, name_pattern: Optional[str] = None) -> Dict:
        """
        Proceso principal de migración con lista predefinida de monitores
        """
        results = {
            "total_monitors": 0,
            "successful_migrations": 0,
            "failed_migrations": 0,
            "monitors": []
        }
        
        # Paso 1: Lista predefinida de monitores para migración
        print("Procesando lista predefinida de monitores...")
        monitors_list = [
            {"guid": "9232815e-d30c-4481-b906-15e245e09482", "name": "A Jenkins Core common-services-us"},
            {"guid": "7b7e9653-59c2-4b2a-a6e9-98462fe60ef0", "name": "CLVT-US-ALM-CommonServices-Beta-CommonServicesBeta"},
            {"guid": "b3a129ef-d19a-47b1-a480-a100d9c303c5", "name": "CLVT-US-ALM-CommonServices-Prd-CommonServices"},
            {"guid": "7f8b86ca-34be-4027-b45e-c20d64ae9d80", "name": "CCDM Common Service Prod"}
        ]
        
        # Filtrar por patrón si se especifica
        if name_pattern:
            filtered_list = []
            for monitor in monitors_list:
                if name_pattern.lower() in monitor['name'].lower():
                    filtered_list.append(monitor)
            monitors_list = filtered_list
            print(f"Filtrados {len(monitors_list)} monitores que contienen '{name_pattern}'")

        if not monitors_list:
            print("No se encontraron monitores que coincidan con el patrón")
            return results
        
        results["total_monitors"] = len(monitors_list)
        
        # Mostrar tabla de monitores a procesar
        print(f"\nMonitores a procesar ({len(monitors_list)}):")
        for i, monitor in enumerate(monitors_list, 1):
            print(f"  {i}. {monitor['name']} (ID: {monitor['guid'][:8]}...)")
        
        # Paso 2: Procesar cada monitor individualmente
        print(f"\nProcesando {len(monitors_list)} monitores...")
        
        for i, monitor_info in enumerate(monitors_list, 1):
            try:
                print(f"[{i}/{len(monitors_list)}] Procesando: {monitor_info['name']}")
                
                # Obtener detalles completos del monitor
                full_monitor = self.uptrends_client.get_monitor_details(monitor_info['guid'])
                
                if not full_monitor:
                    print(f"No se pudieron obtener detalles de {monitor_info['name']}")
                    results["failed_migrations"] += 1
                    continue
                
                # Procesar monitor
                migration_result = self._process_monitor(full_monitor)
                results["monitors"].append(migration_result)
                
                if migration_result["success"]:
                    results["successful_migrations"] += 1
                    print(f"✅ {full_monitor.name} → {migration_result['elastic_type']}")
                else:
                    results["failed_migrations"] += 1
                    print(f"❌ {full_monitor.name}: {migration_result['errors']}")
                    
            except Exception as e:
                print(f"Error procesando {monitor_info['name']}: {e}")
                results["failed_migrations"] += 1
        
        # Guardar resultados
        self._save_migration_results(results)
        
        return results
    
    def _process_monitor(self, monitor: UptrendsMonitor) -> Dict:
        """
        Procesa un monitor individual
        """
        result = {
            "monitor_name": monitor.name,
            "monitor_guid": monitor.monitor_guid,
            "original_type": monitor.monitor_type.value,
            "success": False,
            "elastic_type": None,
            "confidence": 0.0,
            "errors": []
        }
        
        try:
            # Preparar datos para clasificación
            monitor_data = {
                "name": monitor.name,
                "monitor_type": monitor.monitor_type.value,
                "url": monitor.url,
                "http_method": monitor.http_method,
                "check_interval": monitor.check_interval,
                "request_headers": monitor.request_headers,
                "request_body": monitor.request_body,
                "expected_http_status_code": monitor.expected_http_status_code,
                "user_agent": monitor.user_agent,
                "load_time_limit1": monitor.load_time_limit1,
                "load_time_limit2": monitor.load_time_limit2,
                "authentication_type": monitor.authentication_type,
                "username": monitor.username,
                "self_service_transaction_script": monitor.self_service_transaction_script,
                "multi_step_api_transaction_script": monitor.multi_step_api_transaction_script,
                "msa_steps": monitor.msa_steps,
                "transaction_step_definition": monitor.transaction_step_definition,
                "browser_type": monitor.browser_type,
                "browser_window_dimensions": monitor.browser_window_dimensions,
                "dns_server": monitor.dns_server,
                "dns_query": monitor.dns_query,
                "dns_expected_result": monitor.dns_expected_result,
                "port": monitor.port,
                "notes": monitor.notes,
                "selected_checkpoints": monitor.selected_checkpoints
            }
            
            # Clasificar usando IA
            classification = self.ai_classifier.classify_monitor(monitor_data)
            
            # Validar clasificación
            is_valid, errors = self.ai_classifier.validate_classification(classification)
            
            if not is_valid:
                result["errors"] = errors
                return result
            
            # Generar archivo de monitor para Node.js
            monitor_config = self._generate_monitor_config(monitor, classification)
            
            # Validar configuración del monitor con validador estricto
            config_valid, config_errors = self.monitor_validator.validate_monitor_config(
                monitor_config, classification.elastic_type.value
            )
            
            if not config_valid:
                result["errors"] = config_errors
                return result
            
            # Validar script de browser si aplica
            if classification.elastic_type.value == "browser":
                script = self._generate_browser_script(monitor)
                script_valid, script_errors = self.monitor_validator.validate_browser_script(script)
                if not script_valid:
                    result["errors"] = script_errors
                    return result
            
            # Guardar archivo
            filename = self._save_monitor_file(monitor, classification, monitor_config)
            
            result.update({
                "success": True,
                "elastic_type": classification.elastic_type.value,
                "confidence": classification.confidence,
                "reasoning": classification.reasoning,
                "output_file": filename
            })
            
        except Exception as e:
            result["errors"] = [str(e)]
            
        return result
    
    def _generate_monitor_config(self, monitor: UptrendsMonitor, classification: MonitorClassification) -> Dict:
        """
        Genera la configuración del monitor para Elastic Synthetics
        """
        base_config = {
            "name": monitor.name,
            "id": f"monitor-{monitor.monitor_guid}",
            "type": classification.elastic_type.value,
            "enabled": monitor.is_active,
            "schedule": classification.recommended_config.get("schedule", "@every 5m"),
            "timeout": classification.recommended_config.get("timeout", "30s"),
            "locations": classification.recommended_config.get("locations", ["us_central"]),
            "tags": ["migrated-from-uptrends"],
            "original_uptrends_id": monitor.monitor_guid
        }
        
        # Configuración específica por tipo
        if classification.elastic_type.value == "http":
            base_config.update({
                "urls": [monitor.url],
                "max_redirects": classification.recommended_config.get("max_redirects", 3),
                "mode": "any"
            })
            
            if monitor.http_method:
                base_config["method"] = monitor.http_method
                
            if monitor.request_headers:
                base_config["headers"] = monitor.request_headers
                
            if monitor.request_body:
                base_config["body"] = monitor.request_body
                
            if monitor.expected_http_status_code:
                base_config["check.response.status"] = [monitor.expected_http_status_code]
                
            if monitor.match_pattern:
                base_config["check.response.body.positive"] = [monitor.match_pattern]
                
        elif classification.elastic_type.value == "tcp":
            # Extraer host y puerto de la URL
            from urllib.parse import urlparse
            parsed = urlparse(monitor.url)
            base_config.update({
                "hosts": [f"{parsed.hostname}:{parsed.port or 80}"],
                "check.send": "",
                "check.receive": ""
            })
            
        elif classification.elastic_type.value == "icmp":
            from urllib.parse import urlparse
            parsed = urlparse(monitor.url)
            base_config.update({
                "hosts": [parsed.hostname or monitor.url],
                "wait": "1s"
            })
            
        elif classification.elastic_type.value == "browser":
            # Para monitores de navegador, se requiere un script separado
            base_config.update({
                "source": {
                    "inline": {
                        "script": self._generate_browser_script(monitor)
                    }
                },
                "params": {
                    "url": monitor.url
                }
            })
        
        return base_config
    
    def _generate_browser_script(self, monitor: UptrendsMonitor) -> str:
        """
        Genera un script para desplegar en Elastic Synthetics un monitor de tipo browser basado en el monitor de Uptrends asegurate de que el monitor funcione mas alla de la perfeccion quiero algo de que pueda mejorar pero funcional
        """
        if monitor.self_service_transaction_script:
            # Intentar convertir script de Uptrends a Playwright
            return f"""
import {{ journey, step, expect }} from '@elastic/synthetics';

journey('{monitor.name}', ({{ page, params }}) => {{
    step('Navigate to URL', async () => {{
        await page.goto(params.url);
    }});
    
    step('Verify page loaded', async () => {{
        await expect(page).toHaveTitle(/.*/);
    }});
    
    // TODO: Convertir script de Uptrends:
    // {monitor.self_service_transaction_script}
}});
"""
        else:
            return f"""
import {{ journey, step, expect }} from '@elastic/synthetics';

journey('{monitor.name}', ({{ page, params }}) => {{
    step('Navigate to URL', async () => {{
        await page.goto(params.url);
    }});
    
    step('Verify page response', async () => {{
        const response = await page.waitForResponse(params.url);
        expect(response.status()).toBe({monitor.expected_http_status_code or 200});
    }});
}});
"""
    
    def _save_monitor_file(self, monitor: UptrendsMonitor, classification: MonitorClassification, config: Dict) -> str:
        """
        Guarda el archivo de configuración del monitor en el directorio apropiado
        """
        # Crear nombre de archivo seguro
        safe_name = "".join(c for c in monitor.name if c.isalnum() or c in (' ', '-', '_')).strip()
        safe_name = safe_name.replace(' ', '_').lower()
        
        # Determinar directorio y formato según tipo
        if classification.elastic_type.value == "browser":
            # Monitores browser van en directorio journey
            output_dir = self.journey_dir
            filename = f"{safe_name}.journey.ts"
            content = self._generate_browser_script(monitor)
        else:
            # Monitores lightweight (http, tcp, icmp) van en directorio lightweight
            output_dir = self.lightweight_dir
            filename = f"{safe_name}.yml"
            import yaml
            content = yaml.dump(config, default_flow_style=False)
        
        filepath = output_dir / filename
        
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(content)
        
        return f"{output_dir.name}/{filename}"
    
    def _display_monitors_table(self, monitors: List[UptrendsMonitor]):
        """
        Muestra tabla con monitores encontrados
        """
        print("\nMonitores encontrados en Uptrends:")
        print("-" * 80)
        for i, monitor in enumerate(monitors, 1):
            status = "✅ Activo" if monitor.is_active else "❌ Inactivo"
            print(f"{i:2d}. {monitor.name}")
            print(f"    Tipo: {monitor.monitor_type.value}")
            print(f"    URL: {monitor.url}")
            print(f"    Estado: {status}")
            print()
    
    def _display_monitors_list_table(self, monitors_list: List[Dict]):
        """
        Muestra tabla con lista básica de monitores
        """
        print("\nMonitores encontrados en Uptrends:")
        print("-" * 80)
        for i, monitor_info in enumerate(monitors_list, 1):
            status = "✅ Activo" if monitor_info.get('is_active', True) else "❌ Inactivo"
            print(f"{i:2d}. {monitor_info['name']}")
            print(f"    GUID: {monitor_info['guid'][:8]}...")
            print(f"    Tipo: {monitor_info.get('type', 'N/A')}")
            print(f"    Estado: {status}")
            print()
    
    def _save_migration_results(self, results: Dict):
        """
        Guarda los resultados de la migración
        """
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        results_file = self.base_output_dir / f"migration_results_{timestamp}.json"
        
        # Agregar estadísticas por tipo de monitor
        monitor_stats = {
            "lightweight": 0,
            "journey": 0
        }
        
        for monitor in results["monitors"]:
            if monitor["success"]:
                if monitor["elastic_type"] == "browser":
                    monitor_stats["journey"] += 1
                else:
                    monitor_stats["lightweight"] += 1
        
        results["monitor_stats"] = monitor_stats
        
        with open(results_file, 'w', encoding='utf-8') as f:
            json.dump(results, f, indent=2, ensure_ascii=False)
        
        print(f"Resultados guardados en: {results_file}")
        print(f"Monitores lightweight: {monitor_stats['lightweight']}")
        print(f"Monitores journey: {monitor_stats['journey']}")

