from django.conf import settings


class DatabaseAppsRouter(object):

    def db_for_read(self, model, **hints):
        if model._meta.app_label == 'dkapp':
            return 'dkdb'
        else:
            return None

    def db_for_write(self, model, **hints):
        if model._meta.app_label == 'dkapp':
            return 'dkdb'
        else:
            return None

    def allow_migrate(self, db, app_label, model_name=None, **hints):
        if app_label == 'dkapp':
            return db == 'dkdb'
        else:
            return db == 'default'
