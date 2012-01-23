#coding:utf-8

'''
    flaskext.admin
    ~~~~~~~~~~~~~~

    Flask-Mongodb-Admin is a Flask extension module.

    :copyright: (c) 2011 by Oleg Lebedev.
    :license: MIT, see LICENSE for more details.
'''

import os
import inspect
import json
import re
from datetime import datetime

from flask import (Blueprint, render_template,
                   abort, request, flash, redirect,
                   url_for, Response)
from flask.views import MethodView
from flaskext.login import login_required
from flaskext.principal import Permission, Need
from wtforms.form import FormMeta
from wtforms.widgets import HTMLString, html_params
from flaskext import wtf

PERMISSIONS = Permission(Need('role', 'admin'))

def _get_admin_dir():
    ''' get absolute path to flaskext.admin folder '''
    return os.path.dirname(inspect.getfile(inspect.currentframe()))

APP = Blueprint(
        'admin', 'admin',
        static_folder=os.path.join(_get_admin_dir(), 'static'),
        template_folder=os.path.join(_get_admin_dir(), 'templates'),
    )

APP.dict_models = {}
PAGE_LIMIT = 100
FIELDS_PREFIX = 'id_'

REQ = [wtf.validators.required(u'Обязательное поле.')]

def wrap_model(model):
    ''' обертка для добовления необходимых 
        свойств и методов, не пригодилась '''
    return model

def register(model):
    ''' регистрирую модели и оборачиваю их для
        добавления необходимых атрибутов и методов '''
    APP.dict_models[model.__name__.lower()] = wrap_model(model)

class ModelSet(object):
    '''
        Wrapper for models & handlers 
    '''
    def __init__(self, field, wrap, unwrap):
        self.field  = field
        self.wrap   = wrap
        self.unwrap = unwrap

# здесь функции подготовки к заполнению форм
# и обратные им

DUMMY = lambda x: x

def wrap_d(ex):
    ''' convert date to isoformat string'''
    return ex.isoformat()

def parse_d(ex):
    ''' parse string to datetime object '''
    return datetime(*map(int, re.split('[^\d]', ex)[:-1]))

def wrap_reference(ex):
    ''' return `int` ID of given object
        if hasattr '''
    if hasattr(ex, 'id'):
        return ex.id
    return ex

def unwrap_reference(ex, _obj):
    ''' depricated function '''
    return ex

def wrap_manyreference(ex):
    ''' depricated function '''
    return ex

class ImageInput(object):
    ''' немного правлю виджет для картинок '''

    _item_id = 0

    def __init__(self, prop, model):
        if isinstance(model.id, (long, int)):
            self._prop = prop
            self._item_id = model.id if (hasattr(model, 'id')) else 0
            self._model = model
            self._name = model.__name__.lower() \
                            if hasattr(model, '__name__')\
                            else model.__class__.__name__.lower()
        else:
            self._prop = prop
            self._item_id = 0
            self._model = model
            self._name = model.__name__.lower() \
                            if hasattr(model, '__name__')\
                            else model.__class__.__name__.lower()
                            
    def __call__(self, field, **kwargs):
        kwargs.setdefault('id', field.id)
        value = field._value()
        if value:
            kwargs.setdefault('value', value)
        return HTMLString(u'<input %s /> <img src="%s">' \
                          % (html_params(name=field.name,
                                         type=u'file', **kwargs),
                             url_for(
                                    'admin.view/image',
                                    model=self._name,
                                    prop=self._prop,
                                    id=self._item_id
                                ))
                        )

class IntField(wtf.IntegerField):
    ''' Переоределяю метод, для возможности оставить поле пустым '''

    def process_formdata(self, valuelist):
        if valuelist and not valuelist[0] is u'':
            try:
                self.data = long(valuelist[0])
            except ValueError:
                raise ValueError(self.gettext(u'Not a valid integer value'))

class FileS3(object):

    ''' Отображаю поле с файлом + ссылка '''

    def __call__(self, field, **kwargs):
        kwargs.setdefault('id', field.id)
        value = field._value()
        if value:
            kwargs.setdefault('value', value)
        return HTMLString(u'<input %s /> <a target="_blank" href=%s>%s</a>' %
                                    (
                                        html_params(name=field.name,
                                                    type=u'file', **kwargs),
                                        value,
                                        '...'+value[-20:],
                                    ))

FIELDS_DICT = dict(
    # словарь, для обработки полей
    ListField     = ModelSet(wtf.TextAreaField, json.dumps, json.loads),
    RefField      = ModelSet(wtf.SelectField, wrap_reference,
                             unwrap_reference),
    BoolField     = ModelSet(wtf.BooleanField, DUMMY, DUMMY),
    StringField   = ModelSet(wtf.TextAreaField, DUMMY, DUMMY),
    IntField      = ModelSet(IntField, DUMMY, DUMMY),
    AnythingField = ModelSet(wtf.TextAreaField, json.dumps, json.loads),
    LongField     = ModelSet(IntField, DUMMY, DUMMY),
    DateTimeField = ModelSet(wtf.TextField, wrap_d, parse_d),
    ManyRefField  = ModelSet(wtf.SelectMultipleField,
                             wrap_manyreference,
                             unwrap_reference),
    KVField       = ModelSet(wtf.TextAreaField, json.dumps, json.loads),
    BinaryField   = ModelSet(wtf.FileField, lambda x: None,
                             lambda x: x.read()),
    FileS3Field   = ModelSet(wtf.FileField, DUMMY, DUMMY),
    ImageS3Field  = ModelSet(wtf.FileField, DUMMY, DUMMY),
)

def _create_form_for(model):
    ''' Create a `Form` object for given model '''
    if hasattr(model, '_from'):
        return model._form

    class MetaForm(FormMeta):
        ''' Генерирую метакласс формы '''

        def set_fields(mcs, key, val):
            ''' здесь нахожу метод для создания поля '''
            if key in ['mongo_id', 'relationship_status']:
                # пропускаю поля: которые ненужно отображать в форме
                return
            if hasattr(mcs, u'set_%s' % val.__class__.__name__.lower()):
                getattr(mcs, u'set_%s' % val.__class__.__name__.lower())(key, val)
            else:
                getattr(mcs, u'set_defaultfield')(key, val)

        def set_defaultfield(mcs, key, val):
            ''' deffault field '''
            validators  = REQ if (val.required) else []
            mcs._unbound_fields.append(('%s%s'%(FIELDS_PREFIX, key), \
                           FIELDS_DICT[val.__class__.__name__]\
                           .field(key, validators=validators,)))

        def set_reffield(mcs, key, val):
            '''
                #
            '''
            validators  = REQ if (val.required) else []
            qs = [(i.id, i.__unicode__()) for i in val._obj.query.all()]
            mcs._unbound_fields.append(('%s%s' % (FIELDS_PREFIX, key), \
                           FIELDS_DICT[val.__class__.__name__]\
                           .field(key, validators=validators,
                                  choices=qs, coerce=int)))

        def set_manyreffield(mcs, key, val):
            '''
                #
            '''
            mcs.set_reffield(key, val)

        def set_files3field(mcs, key, val):
            '''
                #
            '''
            validators  = REQ if (val.required) else []
            mcs._unbound_fields.append(('%s%s'%(FIELDS_PREFIX, key), \
                           FIELDS_DICT[val.__class__.__name__]\
                           .field(
                                key,
                                validators=validators,
                                widget=FileS3())))

        def set_images3field(mcs, key, val):
            '''
                #
            '''
            mcs.set_files3field(key, val)

        def set_binaryfield(mcs, key, val):
            '''
                #
            '''
            validators  = REQ if (val.required) else []
            mcs._unbound_fields.append(('%s%s'%(FIELDS_PREFIX, key), \
                           FIELDS_DICT[val.__class__.__name__]\
                           .field(
                                key,
                                validators=validators,
                                widget=ImageInput(key, model))))

        def __call__(mcs, *args, **kwargs):
            '''
                #
            '''
            mcs._unbound_fields = []
            for key, val in model._fields.items():
                mcs.set_fields(key, val)
            return type.__call__(mcs, *args, **kwargs)

    class Fr(wtf.Form):
        ''' подключаю созданный метакласс '''
        __metaclass__ = MetaForm
    return Fr

def _get_values(model):
    ''' gettin values for given model '''
    kwargs = {}
    for key, val in model._fields.items():
        if key in ['relationship_status','mongo_id']:
            continue
        if hasattr(model, key):
            kwargs['%s%s' % (FIELDS_PREFIX, key)] = \
            FIELDS_DICT[val.__class__.__name__].wrap(getattr(model, key))
    return kwargs

class SetValues(object):
    
    ''' Устанавливаю полученые значения в модель.
        Есть возможность добавить в модель
        упаковщик данных с названием ´_%(property)_wrap´
        и он будет вызываться после всего. Это удобно, например для картинок '''

    def __init__(self, model, **kw):
        self.clean_namespace = {}
        self.data = {}
        self.model = model

        for name, raw in kw.items():
            self.clean_namespace[name.replace(FIELDS_PREFIX, '')] = raw

        for key, val in self.model._fields.items():
            self.set_values(key, val)
            if self.clean_namespace.get(key):
                try:
                    # backdoor для возможности упаковки 
                    # данных на уровне модели
                    func = getattr(model, '_%s_wrap' % key)
                    setattr(self.model, key, func(self.data[key]))
                except:
                    setattr(self.model, key, self.data[key])

    def set_values(self, key, val):
        '''
            choice wich method need to call
        '''
        if key in ['mongo_id', 'relationship_status']:
            # пропускаю поля: которые ненужно отображать в форме
            return
        if hasattr(self, u'set_%s' % val.__class__.__name__.lower()):
            getattr(self, u'set_%s' % val.__class__.__name__.lower())(key, val)
        else:
            getattr(self, u'set_defaultfield')(key, val)

    def set_defaultfield(self, key, val):
        '''
            #
        '''
        if self.clean_namespace.get(key):
            self.data[key] = FIELDS_DICT[val.__class__.__name__]\
            .unwrap(self.clean_namespace.get(key))

    def set_reffield(self, key, val):
        '''
            #
        '''
        if self.clean_namespace.get(key):
            self.data[key] = FIELDS_DICT[val.__class__.__name__]\
            .unwrap(self.clean_namespace.get(key), val._obj)

    def set_manyreffield(self, key, val):
        '''
            #
        '''
        self.set_reffield(key, val)

    def set_boolfield(self, key, val):
        '''
            #
        '''
        if self.clean_namespace.get(key):
            self.data[key] = FIELDS_DICT[val.__class__.__name__]\
            .unwrap(self.clean_namespace.get(key))
            setattr(self.model, key, self.data[key])

def to_dict(req):
    '''
        Объеденяю данные из запроса '''
    result = req.form.to_dict()
    result.update(req.files.to_dict())
    return result


class Index(MethodView):
    ''' отображение всех зарегистрированных
        моделей '''
    @login_required
    @PERMISSIONS.require(403)
    def get(self):
        '''
            обрабатываю метод GET
        '''
        context = dict(
            models=APP.dict_models,
        )
        return render_template('index.html', **context)

class ListModel(MethodView):
    ''' Список объектов в коллекции '''
    @login_required
    @PERMISSIONS.require(403)
    def get(self, **kwargs):
        '''
            обрабатываю GET
        '''
        model = APP.dict_models.get(kwargs.get('model'))
        if not model:
            return abort(404)
        page = int(request.form.get('p', request.args.get('p', 1)))
        items =  model.query.descending('mongo_id').paginate(page, PAGE_LIMIT)
        context = dict(
            queryset = items,
            m = model,
        )

        return render_template('list_model.html', **context)

class ViewOne(MethodView):
    ''' Показываю/Сохраняю данные в форме '''
    @login_required
    @PERMISSIONS.require(403)
    def get(self, **kwargs):
        '''
            обрабатываю GET
        '''
        model = APP.dict_models.get(kwargs.get('model'))
        if not model:
            return abort(404)
        item = model.query.get(kwargs.get('id', 0))
        if not item:
            return abort(404)
        values = _get_values(item)
        form = _create_form_for(item)(**values)
        context = dict(
            m = model,
            item = item,
            form = form,
        )
        return render_template('view_one.html', **context)

    @login_required
    @PERMISSIONS.require(403)
    def post(self, **kwargs):
        '''
            обрабатываю POST
        '''
        model = APP.dict_models.get(kwargs.get('model'))
        if not model:
            return abort(404)
        item = model.query.get(kwargs.get('id', 0))
        if not item:
            return abort(404)
        form = _create_form_for(item)(**to_dict(request))
        if not form.validate():
            flash(u'Исправьте ошибки', 'error')
            context = dict(
                m = model,
                item = item,
                form = form,
            )
            return render_template('view_one.html', **context)
        else:
            SetValues(item, **form.data)
            try:
                item._admin_save()
            except AttributeError:
                item.save()
            flash(u'Данные сохранены.', 'success')
            return redirect(
                    url_for(
                        'admin.view/one',
                        model=model.__name__.lower(),
                        id=item.mongo_id)
                   )

class Delete(MethodView):
    ''' Удаляю объект '''
    @login_required
    @PERMISSIONS.require(403)
    def get(self, **kwargs):
        '''
            обрабатываю метод GET
        '''
        model = APP.dict_models.get(kwargs.get('model'))
        if not model:
            return abort(404)
        item = model.query.get(kwargs.get('id', 0))
        if not item:
            return abort(404)
        item.remove()
        flash(u'Успешно удалено.', 'success')
        return redirect(url_for('admin.list/model', model=model.__name__.lower()))

class AddOne(MethodView):
    ''' Добавляю объект '''
    @login_required
    @PERMISSIONS.require(403)
    def get(self, **kwargs):
        '''
            обрабатываю GET
            пустая форма
        '''
        model = kwargs.get('m', APP.dict_models.get(kwargs.get('model')))
        if not model:
            return abort(404)
        form = kwargs.get('form', _create_form_for(model)())
        context = dict(
            m = model,
            form = form,
        )
        return render_template('add_one.html', **context)

    @login_required
    @PERMISSIONS.require(403)
    def post(self, **kwargs):
        '''
            обрабатываю метод POST
        '''
        model = APP.dict_models.get(kwargs.get('model'))
        if not model:
            return abort(404)
        form = _create_form_for(model)(**to_dict(request))
        if not form.validate():
            flash(u'Исправьте ошибки', 'error')
            context = dict(
                m = model,
                form = form,
            )
            return self.get(**context)
        else:
            item = model()
            SetValues(item, **form.data)
            try:
                item._admin_save()
            except AttributeError:
                item.save()
            flash(u'Данные сохранены.', 'success')
            return redirect(
                    url_for(
                        'admin.view/one',
                        model=model.__name__.lower(),
                        id=item.mongo_id
                        )
                   )

class ViewImage(MethodView):
    ''' Рендерю картинки из binaryfield '''
    @login_required
    @PERMISSIONS.require(403)
    def get(self, **kwargs):
        '''
            обрабатываю метод GET
        '''
        model = APP.dict_models.get(kwargs.get('model'))
        if not model:
            return abort(404)
        item = model.query.get(kwargs.get('id', 0))
        if not item:
            return abort(404)
        if not hasattr(item, kwargs.get('prop', '_')):
            return abort(404)
        return Response(
                getattr(item, kwargs.get('prop')),
                content_type='image/png'
               )

APP.add_url_rule('/', view_func=Index.as_view('index'))
APP.add_url_rule('/<model>', view_func=ListModel.as_view('list/model'))
APP.add_url_rule('/<model>/<id>', view_func=ViewOne.as_view('view/one'))
APP.add_url_rule('/<model>/<id>/delete', view_func=Delete.as_view('delete'))
APP.add_url_rule('/<model>/add', view_func=AddOne.as_view('add/one'))
APP.add_url_rule('/<model>/<id>/<prop>/image',
                 view_func=ViewImage.as_view('view/image'))

def admin(application, url_prefix='/admin'):
    ''' Подключаю к приложению '''
    application.register_blueprint(APP, url_prefix=url_prefix)
    return application