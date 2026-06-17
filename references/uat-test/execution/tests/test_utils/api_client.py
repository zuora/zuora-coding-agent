"""
Generic API Client for E2E tests.
Handles authentication, request/response logging, and common API operations.
"""

import requests
import json
import logging
import yaml
import os
import time
from typing import Dict, Any, Optional

logger = logging.getLogger(__name__)


def _default_config_path() -> str:
    from tests.test_utils.repo_paths import default_test_config_path

    return default_test_config_path()


class APIClient:
    """Generic client for interacting with REST APIs"""

    RETRYABLE_STATUS_CODES = [502, 503, 504]
    MAX_RETRY_ATTEMPTS = 3
    RETRY_INITIAL_BACKOFF = 2.0
    RETRY_BACKOFF_MULTIPLIER = 2.0
    RETRY_MAX_BACKOFF = 30.0

    def __init__(self, config_path: Optional[str] = None):
        if config_path is None:
            config_path = _default_config_path()
        else:
            norm = config_path.replace("\\", "/")
            if norm.startswith("execution/"):
                from tests.test_utils.repo_paths import execution_root

                tail = norm.split("execution/", 1)[-1].lstrip("/")
                config_path = str(execution_root() / tail)
        if not os.path.isabs(config_path):
            if os.path.exists(config_path):
                pass
            else:
                from tests.test_utils.repo_paths import execution_root

                current_dir = os.path.dirname(os.path.abspath(__file__))
                ex_dir = os.path.dirname(os.path.dirname(current_dir))
                joined = os.path.join(ex_dir, config_path)
                if os.path.exists(joined):
                    config_path = joined
                else:
                    ex_config = os.path.join(execution_root(), "config", "test_config.yaml")
                    if os.path.exists(ex_config):
                        config_path = ex_config
                    else:
                        cwd_exec = os.path.join("execution", "config", "test_config.yaml")
                        if os.path.exists(cwd_exec):
                            config_path = cwd_exec

        self.config = self._load_config(config_path)
        self.test_environment = self._get_test_environment()
        self.base_url = self.test_environment.get('api_base_url', self.test_environment.get('rest_url', ''))
        self.access_token = None
        self.session = requests.Session()
        self.last_request_url = None
        self.last_request_method = None

        self.session.headers.update({
            'Content-Type': 'application/json',
            'Accept': 'application/json'
        })

        if 'custom_headers' in self.test_environment and self.test_environment['custom_headers']:
            self.session.headers.update(self.test_environment['custom_headers'])

    def _mcp_implicit_config(self) -> Optional[Dict[str, Any]]:
        """Build minimal config from ZUORA_* env when no test_config.yaml exists."""
        base = os.environ.get("ZUORA_BASE_URL", "").strip()
        if not base:
            return None
        ui_base = os.environ.get("ZUORA_UI_BASE_URL", "").strip()
        if not ui_base:
            host = base.replace("https://", "").replace("http://", "").split("/")[0]
            if host.startswith("rest-"):
                host = host[5:]
            elif host.startswith("rest."):
                host = host[5:]
            ui_base = f"https://{host}/apps"
        auth: Dict[str, Any]
        if os.environ.get("ZUORA_BEARER_TOKEN"):
            auth = {"type": "bearer", "token": os.environ["ZUORA_BEARER_TOKEN"]}
        elif os.environ.get("ZUORA_CLIENT_ID") and os.environ.get("ZUORA_CLIENT_SECRET"):
            auth = {
                "type": "oauth",
                "client_id": os.environ["ZUORA_CLIENT_ID"],
                "client_secret": os.environ["ZUORA_CLIENT_SECRET"],
                "token_endpoint": "/oauth/token",
                "grant_type": "client_credentials",
            }
        else:
            return None
        return {
            "default_environment": "mcp",
            "test_environments": {
                "mcp": {
                    "api_base_url": base,
                    "ui_base_url": ui_base,
                    "authentication": auth,
                }
            },
        }

    def _load_config(self, config_path: str) -> Dict[str, Any]:
        try:
            with open(config_path, 'r', encoding='utf-8') as f:
                data = yaml.safe_load(f)
            if data:
                return data
            implicit = self._mcp_implicit_config()
            if implicit:
                logger.info("Config at %s is empty; using MCP implicit tenant from env", config_path)
                return implicit
            raise ValueError(f"Configuration file is empty or comment-only: {config_path}")
        except FileNotFoundError:
            implicit = self._mcp_implicit_config()
            if implicit:
                logger.info("No config at %s; using MCP implicit tenant from env", config_path)
                return implicit
            logger.error("Configuration file not found: %s", config_path)
            raise
        except yaml.YAMLError as e:
            logger.error("Error parsing configuration file: %s", e)
            raise

    def _resolve_base_environment_name(self, env_override: Optional[str], default_env: str) -> str:
        """Resolve TEST_ENVIRONMENT to a key in test_environments.

        Keys with underscores (e.g. sandbox_cloud_us) are valid when listed in config.
        Unknown suffixed values (e.g. staging_billing_report_execution) are rejected;
        use get_tenant_by_suffix() for those tenants instead.
        """
        test_environments = self.config.get('test_environments', {})
        if not env_override:
            return default_env
        if env_override in test_environments:
            logger.info("Using environment override: %s", env_override)
            return env_override
        if '_' in env_override:
            logger.warning(
                "TEST_ENVIRONMENT='%s' is not a configured environment key. "
                "Use get_tenant_by_suffix() for suffixed tenants. "
                "Falling back to default_environment.",
                env_override,
            )
            return default_env
        logger.warning(
            "Environment '%s' not found, falling back to default_environment",
            env_override,
        )
        return default_env

    def _get_test_environment(self) -> Dict[str, Any]:
        """Get base test environment configuration from test_environments."""
        if 'test_environments' in self.config:
            default_env = self.config.get('default_environment', 'staging')
            env_override = os.getenv('TEST_ENVIRONMENT')
            selected_env = self._resolve_base_environment_name(env_override, default_env)

            if selected_env not in self.config['test_environments']:
                logger.warning("Environment '%s' not found, falling back to 'staging'", selected_env)
                selected_env = 'staging'

            return self.config['test_environments'][selected_env]
        elif 'test_environment' in self.config:
            logger.info("Using legacy config structure")
            return self.config['test_environment']
        else:
            raise ValueError("No test environment configuration found in config file")

    @classmethod
    def create_for_environment(cls, environment_name: str, config_path: Optional[str] = None):
        original_env = os.getenv('TEST_ENVIRONMENT')
        os.environ['TEST_ENVIRONMENT'] = environment_name
        try:
            client = cls(config_path)
            return client
        finally:
            if original_env is not None:
                os.environ['TEST_ENVIRONMENT'] = original_env
            else:
                os.environ.pop('TEST_ENVIRONMENT', None)

    def authenticate(self) -> bool:
        """Authenticate with API using configured authentication method.

        If ZUORA_BEARER_TOKEN and ZUORA_BASE_URL env vars are set (injected by
        the pipeline orchestrator), they take priority over test_config.yaml.
        """
        env_bearer = os.environ.get('ZUORA_BEARER_TOKEN')
        env_base_url = os.environ.get('ZUORA_BASE_URL')
        if env_bearer and env_base_url:
            self.base_url = env_base_url
            self.session.headers['Authorization'] = f"Bearer {env_bearer}"
            logger.info("Using ZUORA_BEARER_TOKEN from environment.")
            return True

        auth_config = self.test_environment.get('authentication', {})
        auth_type = auth_config.get('type', 'oauth')

        try:
            if auth_type == 'oauth':
                return self._authenticate_oauth(auth_config)
            elif auth_type == 'basic':
                return self._authenticate_basic(auth_config)
            elif auth_type == 'api_key':
                return self._authenticate_api_key(auth_config)
            elif auth_type == 'bearer':
                return self._authenticate_bearer(auth_config)
            else:
                logger.warning(f"Unknown authentication type: {auth_type}, skipping authentication")
                return True
        except Exception as e:
            logger.error(f"Authentication error: {str(e)}")
            return False

    def _authenticate_oauth(self, auth_config: Dict[str, Any]) -> bool:
        auth_url = f"{self.base_url}{auth_config.get('token_endpoint', '/oauth/token')}"
        auth_data = {
            'client_id': auth_config.get('client_id', self.test_environment.get('client_id')),
            'client_secret': auth_config.get('client_secret', self.test_environment.get('client_secret')),
            'grant_type': auth_config.get('grant_type', 'client_credentials')
        }
        headers = {'Content-Type': 'application/x-www-form-urlencoded'}

        logger.info("Authenticating with OAuth...")
        response = requests.post(auth_url, data=auth_data, headers=headers)

        if response.status_code == 200:
            token_data = response.json()
            self.access_token = token_data['access_token']
            self.session.headers['Authorization'] = f"Bearer {self.access_token}"
            logger.info("Authentication successful")
            return True
        else:
            logger.error(f"Authentication failed: {response.status_code} - {response.text}")
            return False

    def _authenticate_basic(self, auth_config: Dict[str, Any]) -> bool:
        from requests.auth import HTTPBasicAuth
        username = auth_config.get('username', self.test_environment.get('username'))
        password = auth_config.get('password', self.test_environment.get('password'))
        self.session.auth = HTTPBasicAuth(username, password)
        logger.info("Basic authentication configured")
        return True

    def _authenticate_api_key(self, auth_config: Dict[str, Any]) -> bool:
        api_key = auth_config.get('api_key', self.test_environment.get('api_key'))
        header_name = auth_config.get('header_name', 'X-API-Key')
        self.session.headers[header_name] = api_key
        logger.info("API key authentication configured")
        return True

    def _authenticate_bearer(self, auth_config: Dict[str, Any]) -> bool:
        token = auth_config.get('token', self.test_environment.get('token'))
        self.session.headers['Authorization'] = f"Bearer {token}"
        logger.info("Bearer token authentication configured")
        return True

    def _is_retryable_status(self, status_code: int) -> bool:
        return status_code in self.RETRYABLE_STATUS_CODES

    def _calculate_backoff(self, attempt: int) -> float:
        backoff = self.RETRY_INITIAL_BACKOFF * (self.RETRY_BACKOFF_MULTIPLIER ** attempt)
        return min(backoff, self.RETRY_MAX_BACKOFF)

    def _retry_request(self, request_func, *args, **kwargs) -> requests.Response:
        last_response = None
        last_exception = None

        for attempt in range(self.MAX_RETRY_ATTEMPTS):
            try:
                response = request_func(*args, **kwargs)
                logger.info(f"Response status: {response.status_code}")

                if response.status_code == 401:
                    logger.warning("Received 401 Unauthorized, attempting to re-authenticate...")
                    if self.authenticate():
                        response = request_func(*args, **kwargs)
                        logger.info(f"Retry response status: {response.status_code}")
                    else:
                        logger.error("Re-authentication failed")

                if self._is_retryable_status(response.status_code):
                    last_response = response
                    if attempt < self.MAX_RETRY_ATTEMPTS - 1:
                        backoff_time = self._calculate_backoff(attempt)
                        logger.warning(
                            f"Received {response.status_code} (transient error), "
                            f"retrying in {backoff_time:.1f}s (attempt {attempt + 1}/{self.MAX_RETRY_ATTEMPTS})..."
                        )
                        time.sleep(backoff_time)
                        continue
                    else:
                        logger.error(
                            f"Received {response.status_code} after {self.MAX_RETRY_ATTEMPTS} attempts, "
                            f"giving up. Response: {response.text[:500]}"
                        )
                        return response

                return response

            except Exception as e:
                last_exception = e
                if attempt < self.MAX_RETRY_ATTEMPTS - 1:
                    backoff_time = self._calculate_backoff(attempt)
                    logger.warning(
                        f"Request failed with exception: {str(e)}, "
                        f"retrying in {backoff_time:.1f}s (attempt {attempt + 1}/{self.MAX_RETRY_ATTEMPTS})..."
                    )
                    time.sleep(backoff_time)
                    continue
                else:
                    logger.error(f"Request failed after {self.MAX_RETRY_ATTEMPTS} attempts")
                    raise

        if last_response is not None:
            return last_response
        if last_exception is not None:
            raise last_exception
        raise Exception("Request failed without response or exception")

    def post(self, endpoint: str, data: Any, **kwargs) -> requests.Response:
        url = f"{self.base_url}{endpoint}"
        self.last_request_url = f"POST {url}"
        self.last_request_method = "POST"
        logger.info(f"POST {url}")
        try:
            response = self._retry_request(self.session.post, url, json=data, **kwargs)
            return response
        except Exception as e:
            logger.error(f"POST request failed: {str(e)}")
            raise

    def get(self, endpoint: str, params: Optional[Dict[str, Any]] = None, **kwargs) -> requests.Response:
        url = f"{self.base_url}{endpoint}"
        self.last_request_url = f"GET {url}"
        self.last_request_method = "GET"
        logger.info(f"GET {url}")
        try:
            response = self._retry_request(self.session.get, url, params=params, **kwargs)
            return response
        except Exception as e:
            logger.error(f"GET request failed: {str(e)}")
            raise

    def put(self, endpoint: str, data: Optional[Dict[str, Any]] = None, **kwargs) -> requests.Response:
        url = f"{self.base_url}{endpoint}"
        self.last_request_url = f"PUT {url}"
        self.last_request_method = "PUT"
        logger.info(f"PUT {url}")
        try:
            if data is None:
                response = self._retry_request(self.session.put, url, **kwargs)
            else:
                response = self._retry_request(self.session.put, url, json=data, **kwargs)
            return response
        except Exception as e:
            logger.error(f"PUT request failed: {str(e)}")
            raise

    def patch(self, endpoint: str, data: Optional[Dict[str, Any]] = None, **kwargs) -> requests.Response:
        url = f"{self.base_url}{endpoint}"
        self.last_request_url = f"PATCH {url}"
        self.last_request_method = "PATCH"
        logger.info(f"PATCH {url}")
        try:
            if data is None:
                response = self._retry_request(self.session.patch, url, **kwargs)
            else:
                response = self._retry_request(self.session.patch, url, json=data, **kwargs)
            return response
        except Exception as e:
            logger.error(f"PATCH request failed: {str(e)}")
            raise

    def delete(self, endpoint: str, **kwargs) -> requests.Response:
        url = f"{self.base_url}{endpoint}"
        self.last_request_url = f"DELETE {url}"
        self.last_request_method = "DELETE"
        logger.info(f"DELETE {url}")
        try:
            response = self._retry_request(self.session.delete, url, **kwargs)
            return response
        except Exception as e:
            logger.error(f"DELETE request failed: {str(e)}")
            raise

    def post_multipart(self, endpoint: str, files: Dict[str, tuple], **kwargs) -> requests.Response:
        url = f"{self.base_url}{endpoint}"
        self.last_request_url = f"POST {url} (multipart/form-data)"
        self.last_request_method = "POST"
        logger.info(f"POST {url} (multipart/form-data)")

        headers = kwargs.pop('headers', {})
        original_content_type = self.session.headers.get('Content-Type')
        if 'Content-Type' in self.session.headers:
            del self.session.headers['Content-Type']

        try:
            if headers:
                request_headers = self.session.headers.copy()
                request_headers.update(headers)
            else:
                request_headers = self.session.headers

            response = self.session.post(url, files=files, headers=request_headers, **kwargs)
            logger.info(f"Response status: {response.status_code}")
            return response
        except Exception as e:
            logger.error(f"POST multipart request failed: {str(e)}")
            raise
        finally:
            if original_content_type:
                self.session.headers['Content-Type'] = original_content_type

    def is_authenticated(self) -> bool:
        return self.access_token is not None or 'Authorization' in self.session.headers

    def get_last_request_info(self):
        return self.last_request_url

    def get_response_data(self, response: requests.Response) -> Dict[str, Any]:
        try:
            return response.json()
        except json.JSONDecodeError:
            logger.warning("Response is not valid JSON")
            return {}

    def get_tenant_by_suffix(self, suffix: str) -> Dict[str, Any]:
        """Get tenant configuration by suffix name.

        Appends the suffix to the current base environment to find the tenant.
        Falls back to the base environment if suffixed tenant doesn't exist.
        """
        if 'test_environments' not in self.config:
            raise ValueError("test_environments not found in config.")

        default_env = self.config.get('default_environment', 'staging')
        env_override = os.getenv('TEST_ENVIRONMENT')
        base_env = self._resolve_base_environment_name(env_override, default_env)

        suffixed_env = f"{base_env}_{suffix}"

        if suffixed_env in self.config['test_environments']:
            logger.info("Found suffixed tenant: %s", suffixed_env)
            return self.config['test_environments'][suffixed_env]
        else:
            logger.info("Suffixed tenant '%s' not found, falling back to '%s'", suffixed_env, base_env)
            if base_env not in self.config['test_environments']:
                logger.warning("Base environment '%s' not found, falling back to 'staging'", base_env)
                base_env = 'staging'
            return self.config['test_environments'][base_env]

    def switch_to_tenant(self, tenant_config: Dict[str, Any]) -> bool:
        """Switch API client to use a different tenant configuration."""
        try:
            self.test_environment = tenant_config
            self.base_url = tenant_config.get('api_base_url', tenant_config.get('rest_url', ''))

            if 'custom_headers' in tenant_config and tenant_config['custom_headers']:
                self.session.headers.update(tenant_config['custom_headers'])

            auth_success = self.authenticate()
            if auth_success:
                logger.info("Successfully switched to tenant: %s", tenant_config.get('name', 'unknown'))
            else:
                logger.error("Failed to authenticate with new tenant credentials")
            return auth_success
        except Exception as e:
            logger.error(f"Error switching to tenant: {str(e)}")
            return False

    def handle_error_response(self, response: requests.Response) -> str:
        status_code = response.status_code
        response_text = response.text[:500] if response.text else "(empty response)"

        logger.error(f"Error response - Status: {status_code}, Headers: {dict(response.headers)}, Body: {response_text}")

        if status_code in [502, 503, 504]:
            return f"HTTP {status_code} (Gateway/Proxy Error): {response_text}. This may be a temporary upstream server issue."

        try:
            error_data = response.json()
            if 'reasons' in error_data:
                reasons = error_data['reasons']
                if isinstance(reasons, list) and len(reasons) > 0:
                    return reasons[0].get('message', 'Unknown error')
            elif 'message' in error_data:
                return error_data['message']
            elif 'error' in error_data:
                return error_data['error']
            else:
                return f"HTTP {status_code}: {response_text}"
        except json.JSONDecodeError:
            return f"HTTP {status_code}: {response_text}"
