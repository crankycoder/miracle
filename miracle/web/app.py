from pyramid.config import Configurator
from pyramid.tweens import EXCVIEW

from miracle.api.views import configure as configure_api_views
from miracle.crypto import create_crypto
from miracle.kinesis import create_kinesis
from miracle.log import (
    configure_logging,
    create_raven,
    create_stats,
)
from miracle.web.views import configure as configure_web_views

_APP = None


def application(environ, start_response):  # pragma: no cover
    global _APP
    if _APP is None:
        _APP = create_app()
        if environ is None and start_response is None:
            # Called as part of gunicorn's post_worker_init
            return _APP

    return _APP(environ, start_response)


def create_app(_crypto=None, _kinesis=None, _raven=None, _stats=None):
    configure_logging()
    raven = create_raven(transport='gevent', _raven=_raven)

    try:
        config = Configurator(settings={})
        config.add_tween('miracle.log.log_tween_factory', under=EXCVIEW)

        configure_api_views(config)
        configure_web_views(config)

        config.registry.crypto = create_crypto(_crypto=_crypto)
        config.registry.kinesis = create_kinesis(_kinesis=_kinesis)
        config.registry.raven = raven
        config.registry.stats = create_stats(_stats=_stats)

        wsgi_app = config.make_wsgi_app()
    except Exception:  # pragma: no cover
        raven.captureException()
        raise

    return wsgi_app


def shutdown_app(app):
    registry = getattr(app, 'registry', None)
    if registry is not None:
        del registry.crypto
        registry.kinesis.close()
        del registry.kinesis
        del registry.raven
        registry.stats.close()
        del registry.stats


def worker_exit(server, worker):  # pragma: no cover
    shutdown_app(_APP)
