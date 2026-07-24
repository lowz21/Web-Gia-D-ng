"""Background job: hủy đơn QR quá hạn thanh toán."""
import logging

from apscheduler.schedulers.background import BackgroundScheduler

from services.order_payment import cancel_expired_pending_orders

logger = logging.getLogger(__name__)
_scheduler = None


def _run_expire_job():
    try:
        n = cancel_expired_pending_orders()
        if n:
            logger.info("Đã hủy %s đơn pending_payment quá hạn", n)
    except Exception:
        logger.exception("Lỗi job hủy đơn quá hạn")


def start_scheduler(app):
    global _scheduler
    if _scheduler is not None:
        return _scheduler

    if app.config.get("TESTING"):
        return None

    _scheduler = BackgroundScheduler(daemon=True)
    _scheduler.add_job(
        _run_expire_job,
        "interval",
        minutes=1,
        id="cancel_expired_pending_orders",
        replace_existing=True,
    )
    _scheduler.start()
    with app.app_context():
        _run_expire_job()
    return _scheduler
