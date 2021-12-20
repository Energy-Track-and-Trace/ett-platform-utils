import logging
import flask
from flask import Flask
from flask.testing import FlaskClient
from functools import cached_property
from typing import List, Iterable, Tuple, Any, Optional

from .guards import EndpointGuard
from .endpoint import Endpoint
from .endpoints import HealthCheck
from .orchestration import \
    RequestOrchestrator, JsonBodyProvider, QueryStringProvider


class RequestOrchestratorWrapper(object):
    """
    Wrapper for the request orchestrator.
    By implementation flask does not allow to use multiple view functions
    using the same endpoint/path even though the methods are different.

    This wrapper routes the request to the correct endpoint,
    based on the endpoint path and the method.
    """

    def __init__(self, flask_app: Flask):
        self._orchestrators = {}
        self._flask_app = flask_app

    def path_exists(self, path: str) -> bool:
        return path in self._orchestrators.keys()
    
    def get_path_methods(self, path: str) -> List[str]:
        return self._orchestrators.get(path).keys()

    def add_endpoint(self,
                     method: str,
                     path: str,
                     request_orchestrator: RequestOrchestrator):

        if not self.path_exists(path=path):
            self._orchestrators[path] = {}

        self._orchestrators[path][method] = request_orchestrator

        self.add_url_rule(path=path)
    
    def add_url_rule(self,
                     path: str):
        
        methods = self.get_path_methods(path=path)
        
        self._flask_app.add_url_rule(
            rule=path,
            endpoint=path,
            methods=methods,
            view_func=self,
        )

    def __call__(self, *args, **kwargs):
        method = flask.request.method
        endpoint = flask.request.endpoint

        # Find correct orchestrator with given endpoint and method
        _orchestrator = self._orchestrators.get(endpoint).get(method)

        # Call ocrherator
        return _orchestrator(*args, **kwargs)


class Application(object):
    """
    TODO
    """
    def __init__(self, name: str, secret: str):
        self.name = name
        self.secret = secret

        self.request_orchestrator_wrapper =\
            RequestOrchestratorWrapper(self._flask_app)

    def __call__(self, *args: Any, **kwargs: Any) -> Any:
        return self._flask_app(*args, **kwargs)

    @classmethod
    def create(
            cls,
            *args,
            endpoints: Iterable[Tuple[str, str, Endpoint]] = (),
            health_check_path: Optional[str] = None,
            **kwargs,
    ) -> 'Application':
        """
        Create a new instance of an Application
        """

        app = cls(*args, **kwargs)

        # Add endpoints
        for e in endpoints:
            assert 3 <= len(e) <= 4

            method, path, endpoint = e[:3]

            if len(e) == 4:
                guards = e[3]
            else:
                guards = []

            app.add_endpoint(
                method=method,
                path=path,
                endpoint=endpoint,
                guards=guards,
            )

        # Add health check endpoint
        if health_check_path:
            app.add_endpoint(
                method='GET',
                path=health_check_path,
                endpoint=HealthCheck(),
            )

        return app

    @cached_property
    def _flask_app(self) -> Flask:
        """
        TODO
        """
        return Flask(self.name)

    @property
    def wsgi_app(self) -> Flask:
        """
        TODO
        """
        return self._flask_app

    @property
    def test_client(self) -> FlaskClient:
        """
        TODO
        """
        return self._flask_app.test_client()

    def add_endpoint(
            self,
            method: str,
            path: str,
            endpoint: Endpoint,
            guards: List[EndpointGuard] = None,
    ):
        """
        TODO
        """
        if method == 'GET':
            data_provider = QueryStringProvider()
        elif method == 'POST':
            data_provider = JsonBodyProvider()
        else:
            raise RuntimeError(
                'Unsupported HTTP method for endpoints: %s' % method)

        request_orchestrator = RequestOrchestrator(
            endpoint=endpoint,
            data=data_provider,
            secret=self.secret,
            guards=guards,
        )

        self.request_orchestrator_wrapper.add_endpoint(
            method=method,
            path=path,
            request_orchestrator=request_orchestrator,
        )

    def run_debug(self, host: str, port: int):
        """
        TODO
        """
        self._flask_app.logger.setLevel(logging.DEBUG)
        self._flask_app.run(
            host=host,
            port=port,
            debug=True,
        )
