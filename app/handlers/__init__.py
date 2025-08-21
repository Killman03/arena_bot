from aiogram import Router

from .start import router as start_router
from .goals import router as goals_router

from .finance import router as finance_router
from .finance_upload import router as finance_upload_router
from .finance_management import router as finance_management_router
from .routines import router as routines_router
from .nutrition import router as nutrition_router
from .nutrition_budget import router as nutrition_budget_router
from .todo import router as todo_router
from .productivity import router as productivity_router
from .settings import router as settings_router
from .menus import router as menus_router
from .motivation import router as motivation_router
from .challenges import router as challenges_router
from .test_reminders import router as test_reminders_router
from .settings_menu import router as settings_menu_router
from .analysis import router as analysis_router
from .health import router as health_router
from .zip_import import router as zip_import_router
from .books import router as books_router


def setup_routers() -> Router:
    router = Router()
    router.include_router(start_router)
    router.include_router(goals_router)

    router.include_router(finance_router)
    router.include_router(finance_upload_router)
    router.include_router(finance_management_router)
    router.include_router(routines_router)
    router.include_router(nutrition_router)
    router.include_router(nutrition_budget_router)
    router.include_router(todo_router)
    router.include_router(productivity_router)
    router.include_router(settings_router)
    router.include_router(menus_router)
    router.include_router(motivation_router)
    router.include_router(challenges_router)
    router.include_router(test_reminders_router)
    router.include_router(settings_menu_router)
    router.include_router(analysis_router)
    router.include_router(health_router)
    router.include_router(zip_import_router)
    router.include_router(books_router)
    return router


