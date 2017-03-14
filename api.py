
from datetime import datetime, timedelta, time
from models import Project, Habit, HabitDay, Goal, MiniJournal, User, Task, \
    Readable, Productivity, Event, JournalTag
from google.appengine.ext import ndb
import authorized
import handlers
import tools
import logging
import random
from google.appengine.api import urlfetch
import json
import hashlib
import urllib


class ProjectAPI(handlers.JsonRequestHandler):

    @authorized.role('user')
    def list(self, d):
        self.success = True
        projects = Project.Fetch(self.user)
        self.set_response({
            'projects': [p.json() for p in projects]
        })

    @authorized.role('user')
    def active(self, d):
        self.success = True
        projects = Project.Active(self.user)
        self.set_response({
            'projects': [p.json() for p in projects]
        })

    @authorized.role('user')
    def update(self, d):
        '''
        Create or update
        '''
        id = self.request.get_range('id')
        params = tools.gets(self,
            strings=['title', 'subhead', 'url1', 'url2'],
            booleans=['starred', 'archived'],
            integers=['progress'],
            supportTextBooleans=True
        )
        if id:
            prj = Project.get_by_id(int(id), parent=self.user.key)
        else:
            prj = Project.Create(self.user)
        if prj:
            update_urls = False
            urls = []
            if 'url1' in params:
                urls.append(params.get('url1'))
                update_urls = True
            if 'url2' in params:
                urls.append(params.get('url2'))
                update_urls = True
            if update_urls:
                params['urls'] = urls
            prj.Update(**params)
            prj.put()
            self.success = True
        self.set_response({
            'project': prj.json() if prj else None
        })


class TaskAPI(handlers.JsonRequestHandler):

    @authorized.role('user')
    def list(self, d):
        self.success = True
        tasks = Task.Recent(self.user)
        self.set_response({
            'tasks': [t.json() for t in tasks]
        })

    @authorized.role('user')
    def update(self, d):
        '''
        Create or update
        '''
        id = self.request.get_range('id')
        params = tools.gets(self,
            strings=['title'],
            booleans=['archived', 'wip'],
            integers=['status']
        )
        logging.debug(params)
        if id:
            task = Task.get_by_id(int(id), parent=self.user.key)
        else:
            tz = self.user.get_timezone()
            local_now = tools.local_time(tz)
            schedule_for_same_day = local_now.hour < 16
            local_due = datetime.combine(local_now.date(), time(22, 0)) if schedule_for_same_day else None
            if local_due:
                local_due = tools.server_time(tz, local_due)
            task = Task.Create(self.user, None, due=local_due)
        if task:
            self.message = task.Update(**params)
            self.success = True
            task.put()
        self.set_response({
            'task': task.json() if task else None
        })


class HabitAPI(handlers.JsonRequestHandler):

    @authorized.role('user')
    def list(self, d):
        self.success = True
        habits = Habit.All(self.user)
        self.set_response({
            'habits': [habit.json() for habit in habits]
        })

    @authorized.role('user')
    def recent(self, d):
        '''
        Return recent days of all active habits
        '''
        self.success = True
        days = self.request.get_range('days', default=5)
        habits = Habit.Active(self.user)
        start_date = datetime.today() - timedelta(days=days)
        habitdays = HabitDay.Range(self.user, habits, start_date)
        self.set_response({
            'habits': [habit.json() for habit in habits],
            'habitdays': tools.lookupDict([hd for hd in habitdays if hd],
                    keyprop="key_id",
                    valueTransform=lambda hd: hd.json())
        })

    @authorized.role('user')
    def range(self, d):
        '''
        Return recent days of all active habits
        '''
        self.success = True
        start = self.request.get('start_date')
        end = self.request.get('end_date')
        habits = Habit.Active(self.user)
        habitdays = HabitDay.Range(self.user, habits, tools.fromISODate(start), until_date=tools.fromISODate(end))
        self.set_response({
            'habits': [habit.json() for habit in habits],
            'habitdays': tools.lookupDict([hd for hd in habitdays if hd],
                    keyprop="key_id",
                    valueTransform=lambda hd: hd.json())
        })


    @authorized.role('user')
    def toggle(self, d):
        '''
        Mark done/not-done for a habit day
        '''
        from constants import HABIT_DONE_REPLIES
        habitday_id = self.request.get('habitday_id')
        habit_id = self.request.get_range('habit_id')
        day_iso = self.request.get('date')
        habit = Habit.get_by_id(habit_id, parent=self.user.key)
        hd = None
        if habit and habitday_id:
            marked_done, hd = HabitDay.Toggle(habit, tools.fromISODate(day_iso))
            if marked_done:
                message = random.choice(HABIT_DONE_REPLIES)
            self.success = True
        self.set_response({
            'habitday': hd.json() if hd else None
        })

    @authorized.role('user')
    def commit(self, d):
        '''
        Mark done/not-done for a habit day
        '''
        from constants import HABIT_COMMIT_REPLIES
        habitday_id = self.request.get('habitday_id')
        habit_id = self.request.get_range('habit_id')
        day_iso = self.request.get('date')
        habit = Habit.get_by_id(habit_id, parent=self.user.key)
        if habit and habitday_id:
            hd = HabitDay.Commit(habit, tools.fromISODate(day_iso))
            self.message = random.choice(HABIT_COMMIT_REPLIES)
            self.success = True
        self.set_response({
            'habitday': hd.json() if hd else None
        })

    @authorized.role('user')
    def update(self, d):
        '''
        Create or update
        '''
        id = self.request.get_range('id')
        params = tools.gets(self,
                            strings=['name', 'color', 'icon'],
                            booleans=['archived'],
                            integers=['tgt_weekly'],
                            supportTextBooleans=True
        )
        if id:
            habit = Habit.get_by_id(int(id), parent=self.user.key)
        else:
            habit = Habit.Create(self.user)
        if habit:
            habit.Update(**params)
            habit.put()
            self.success = True
        self.set_response({
            'habit': habit.json() if habit else None
        })


class GoalAPI(handlers.JsonRequestHandler):

    @authorized.role('user')
    def list(self, d):
        self.success = True
        goals = Goal.Recent(self.user)
        self.set_response({
            'goals': [goal.json() for goal in goals]
        })

    @authorized.role('user')
    def current(self, d):
        self.success = True
        [annual, monthly] = Goal.Current(self.user)
        self.set_response({
            'annual': annual.json() if annual else None,
            'monthly': monthly.json() if monthly else None,
        })

    @authorized.role('user')
    def update(self, d):
        '''
        Create or update
        '''
        id = self.request.get('id')
        params = tools.gets(self,
            strings=['text1', 'text2', 'text3', 'text4'],
            integers=['assessment']
        )
        if id:
            goal = Goal.get_by_id(id, parent=self.user.key)
        if not goal:
            annual = len(id) == 4
            goal = Goal.Create(self.user, id=id, annual=annual)
        if goal:
            text = []
            for i in range(1, 5):
                key = 'text%d' % i
                if key in params:
                    text_i = params.get(key)
                    if text_i:
                        text.append(text_i)
            if text:
                params['text'] = text
            goal.Update(**params)
            goal.put()
            self.success = True
        else:
            self.message = "Couldn't create goal"
        self.set_response({
            'goal': goal.json() if goal else None
        })


class EventAPI(handlers.JsonRequestHandler):

    @authorized.role('user')
    def list(self, d):
        page, max, offset = tools.paging_params(self.request)
        events = Event.Fetch(self.user, limit=max, offset=offset)
        self.success = True
        self.set_response({
            'events': [event.json() for event in events]
        }, debug=True)

    @authorized.role('user')
    def update(self, d):
        '''
        Create or update
        '''
        id = self.request.get_range('id')
        params = tools.gets(self,
            strings=['title', 'color'],
            dates=['date_start', 'date_end']
        )
        event = None
        if id:
            event = Event.get_by_id(id, parent=self.user.key)
        if not event:
            event = Event.Create(self.user, params.get('date_start'))
        if event:
            event.Update(**params)
            event.put()
            self.success = True
        else:
            self.message = "Couldn't create event"
        self.set_response({
            'event': event.json() if event else None
        })

    @authorized.role('user')
    def batch_create(self, d):
        events = json.loads(self.request.get('events'))
        dbp = []
        for e in events:
            if 'date_start' in e and isinstance(e['date_start'], basestring):
                e['date_start'] = tools.fromISODate(e['date_start'])
            if 'date_end' in e and isinstance(e['date_end'], basestring):
                e['date_end'] = tools.fromISODate(e['date_end']) if e.get('date_end') else e.get('date_start')
            if not e.get('date_end'):
                e['date_end'] = e.get('date_start')
            e = Event(self.user, **e)
            dbp.append(e)
        if dbp:
            ndb.put_multi(dbp)
            self.success = True
            self.message = "Putting %d" % len(dbp)
        self.set_response()


class ReadableAPI(handlers.JsonRequestHandler):

    @authorized.role('user')
    def list(self, d):
        self.success = True
        readables = Readable.Unread(self.user)
        self.set_response({
            'readables': [r.json() for r in readables]
        })

    @authorized.role('user')
    def update(self, d):
        id = self.request.get('id')
        params = tools.gets(self,
            booleans=['read', 'favorite'])
        r = Readable.get_by_id(id, parent=self.user.key)
        if r:
            r.Update(**params)
            if r.source == 'pocket':
                access_token = self.user.get_integration_prop('pocket_access_token')
                if access_token:
                    from services import pocket
                    if params.get('favorite') == 1:
                        pocket.update_article(access_token, r.source_id, action='favorite')
                    if params.get('read') == 1:
                        pocket.update_article(access_token, r.source_id, action='archive')
            r.put()
            self.success = True
        self.set_response({
            'readable': r.json() if r else None
        })

    @authorized.role('user')
    def delete(self, d):
        id = self.request.get('id')
        r = Readable.get_by_id(id, parent=self.user.key)
        message = None
        if r:
            if r.source == 'pocket':
                access_token = self.user.get_integration_prop('pocket_access_token')
                if access_token:
                    from services import pocket
                    pocket.update_article(access_token, r.source_id, action='delete')
            r.key.delete()
            self.success = True
            self.message = "Deleted item"
        else:
            self.message = "Couldn't find item"
        self.set_response()


class JournalTagAPI(handlers.JsonRequestHandler):

    @authorized.role('user')
    def list(self, d):
        '''
        '''
        tags = JournalTag.All(self.user)
        self.success = True
        self.set_response({
            'tags': [tag.json() for tag in tags]
        })


class JournalAPI(handlers.JsonRequestHandler):

    @authorized.role('user')
    def list(self, d):
        days = self.request.get_range('days', default=4)
        today = datetime.today()
        cursor = today
        journal_keys = []
        for i in range(days):
            iso_date = tools.iso_date(cursor)
            journal_keys.append(ndb.Key('MiniJournal', iso_date, parent=self.user.key))
            cursor -= timedelta(days=1)
        journals = ndb.get_multi(journal_keys)
        self.success = True
        self.set_response({
            'journals': [j.json() for j in journals if j]
            }, debug=True)

    @authorized.role('user')
    def today(self, d):
        '''
        Get today's journal (yesterday if early morning)
        '''
        date = self._get_date()
        jrnl = MiniJournal.Get(self.user, date)
        self.success = True
        self.set_response({
            'journal': jrnl.json() if jrnl else None
        })

    @authorized.role('user')
    def submit(self, d):
        '''
        Submit today's journal (yesterday if 00:00 - 04:00)
        '''
        date = self._get_date()
        task_json = tools.getJson(self.request.get('tasks'))  # JSON
        params = tools.gets(self,
            strings=['lat', 'lon', 'tags_from_text'],
            json=['data'],
            lists=['tags']
        )
        logging.debug(params)
        if params.get('data'):
            # Create new tags from text
            if 'tags_from_text' in params:
                all_tags = JournalTag.CreateFromText(self.user, params.get('tags_from_text'))
                if not params.get('tags'):
                    params['tags'] = []
                for tag in all_tags:
                    if tag.key not in params['tags']:
                        params['tags'].append(tag.key)

            jrnl = MiniJournal.Create(self.user, date)
            jrnl.Update(**params)
            jrnl.put()

            if task_json:
                # Save new tasks for tomorrow
                tasks = []
                due = self._get_task_due_date()
                for t in task_json:
                    if t:
                        task = Task.Create(self.user, t, due=due)
                        tasks.append(task)
                ndb.put_multi(tasks)
            self.success = True

        self.set_response({
            'journal': jrnl.json() if jrnl else None
        })

    def _get_task_due_date(self):
        now = datetime.now()
        return datetime.combine((now + timedelta(hours=24+8)).date(), time(0,0))

    def _get_date(self):
        date = self.request.get('date')
        if not date:
            HOURS_BACK = 8
            now = datetime.now()
            return (now - timedelta(hours=HOURS_BACK)).date()
        else:
            return tools.fromISODate(date).date()


class UserAPI(handlers.JsonRequestHandler):
    @authorized.role('admin')
    def list(self, d):
        page, max, offset = tools.paging_params(self)
        users = User.query().fetch(limit=max, offset=offset)
        self.success = True
        self.set_response({'users': [u.json() for u in users]})

    @authorized.role('user')
    def update_self(self, d):
        params = tools.gets(self, strings=['timezone', 'birthday'], json=['settings'])
        logging.debug(params)
        self.user.Update(**params)
        self.user.put()
        self.update_session_user(self.user)
        message = "%s updated" % self.user
        self.success = True
        self.set_response({'message': message, 'user': self.user.json()})


class AuthenticationAPI(handlers.JsonRequestHandler):
    def google_login(self):
        from constants import ADMIN_EMAIL
        token = self.request.get('token')
        ok, _email, name = self.validate_google_id_token(token)
        if ok:
            u = User.GetByEmail(_email)
            if not u:
                u = User.Create(email=_email, name=name)
                u.put()
            if u:
                self.update_session_user(u)
                self.success = True
                self.message = "Signed in"
        else:
            message = "Failed to validate"
        self.set_response({'user': u.json() if u else None})

    @authorized.role()
    def google_auth(self, d):
        from secrets import GOOGLE_PROJECT_NAME
        client_id = self.request.get('client_id')
        redirect_uri = self.request.get('redirect_uri')
        state = self.request.get('state')
        id_token = self.request.get('id_token')
        redir_url = None
        if client_id == 'google':
            # Part of Google Home / API.AI auth flow
            if redirect_uri == "https://oauth-redirect.googleusercontent.com/r/%s" % GOOGLE_PROJECT_NAME:
                if not self.user:
                    ok, _email, name = self.validate_google_id_token(id_token)
                    if ok:
                        self.user = User.GetByEmail(_email)
                if self.user:
                    access_token = self.user.aes_access_token(client_id='google')
                    redir_url = 'https://oauth-redirect.googleusercontent.com/r/%s#' % GOOGLE_PROJECT_NAME
                    redir_url += urllib.urlencode({
                        'access_token': access_token,
                        'token_type': 'bearer',
                        'state': state
                    })
                    self.success = True
        self.set_response({'redirect': redir_url}, debug=True)

    def validate_google_id_token(self, token):
        import secrets
        success = False
        email = name = None
        g_response = urlfetch.fetch("https://www.googleapis.com/oauth2/v3/tokeninfo?id_token=%s" % token)
        if g_response.status_code == 200:
            json_response = json.loads(g_response.content)
            if 'aud' in json_response:
                aud = json_response['aud']
                if aud == secrets.GOOGLE_CLIENT_ID:
                    success = True
                    email = json_response.get("email", None)
                    name = json_response.get("name", None)
        return (success, email, name)

    @authorized.role()
    def fbook_auth(self, d):
        id_token = self.request.get('id_token')
        account_linking_token = self.request.get('account_linking_token')
        redirect_uri = self.request.get('redirect_uri')
        res = {}
        if not self.user:
            ok, _email, name = self.validate_google_id_token(id_token)
            if ok:
                self.user = User.GetByEmail(_email)
        if self.user:
            auth_code = self.user.key.id()
            if redirect_uri:
                redirect_uri += '&authorization_code=%s' % auth_code
                self.success = True
            else:
                self.message = "No redirect URI?"
        else:
            self.message = "User not found"
        res['redirect'] = redirect_uri
        self.set_response(res, debug=True)

    def logout(self):
        self.success = True
        if self.session.has_key('user'):
            for key in self.session.keys():
                del self.session[key]
        self.message = "Signed out"
        self.set_response()


class AnalysisAPI(handlers.JsonRequestHandler):
    @authorized.role('user')
    def get(self, d):
        # TODO: Async fetches
        with_habits = self.request.get_range('with_habits', default=1) == 1
        with_productivity = self.request.get_range('with_productivity', default=1) == 1
        with_goals = self.request.get_range('with_goals', default=1) == 1
        with_tasks = self.request.get_range('with_tasks', default=1) == 1
        date_start = self.request.get('date_start')
        date_end = self.request.get('date_end')
        dt_start, dt_end = tools.fromISODate(date_start), tools.fromISODate(date_end)
        journal_keys = []
        iso_dates = []
        habits = []
        today = datetime.today()
        if dt_start < dt_end:
            date_cursor = dt_start
            while date_cursor <= dt_end:
                date_cursor += timedelta(days=1)
                iso_date = tools.iso_date(date_cursor)
                journal_keys.append(ndb.Key('MiniJournal', iso_date, parent=self.user.key))
                iso_dates.append(iso_date)
        habitdays = []
        journals = []
        goals = []
        if journal_keys:
            journals = ndb.get_multi(journal_keys)
        if with_habits:
            habits = Habit.Active(self.user)
            habitdays = HabitDay.Range(self.user, habits, dt_start, dt_end)
        if with_productivity:
            productivity = Productivity.Range(self.user, dt_start, dt_end)
        if with_goals:
            goals = Goal.Year(self.user, today.year)
        if with_tasks:
            tasks = Task.DueInRange(self.user, dt_start, dt_end, limit=100)
        self.success = True
        self.set_response({
            'dates': iso_dates,
            'journals': [j.json() for j in journals if j],
            'habits': [h.json() for h in habits],
            'goals': [g.json() for g in goals],
            'tasks': [t.json() for t in tasks],
            'productivity': [p.json() for p in productivity],
            'habitdays': tools.lookupDict([hd for hd in habitdays if hd],
                    keyprop="key_id",
                    valueTransform=lambda hd: hd.json())

            })


class IntegrationsAPI(handlers.JsonRequestHandler):

    @authorized.role('user')
    def update_integration_settings(self, d):
        props = self.request.get('props').split(',')
        for prop in props:
            val = self.request.get(prop)
            self.user.set_integration_prop(prop, val)
        self.user.put()
        self.update_session_user(self.user)
        self.success = True
        self.message = "%d properties saved" % len(props)
        self.set_response({
            'user': self.user.json()
        })

    @authorized.role('user')
    def goodreads_shelf(self, d):
        from services import goodreads
        self.success, readables = goodreads.get_books_on_shelf(self.user, shelf='currently-reading')
        if not self.success:
            self.message = "An error occurred"
        self.set_response({
            'readables': [r.json() for r in readables]
        })

    @authorized.role('user')
    def pocket_sync(self, d):
        '''
        Sync from pocket since last sync
        '''
        from services import pocket
        TS_KEY = 'pocket_last_timestamp'
        access_token = self.user.get_integration_prop('pocket_access_token')
        last_timestamp = self.user.get_integration_prop(TS_KEY, 0)
        self.success, readables, latest_timestamp = pocket.sync(self.user, access_token, last_timestamp)
        self.user.set_integration_prop(TS_KEY, latest_timestamp)
        self.user.put()
        self.update_session_user(self.user)
        self.set_response({
            'readables': [r.json() for r in filter(lambda r: not r.read, readables)]
        })

    @authorized.role('user')
    def pocket_authenticate(self, d):
        '''
        Step 1
        '''
        from services import pocket
        code, redirect = pocket.get_request_token(self.request.host_url)
        if code:
            self.session['pocket_code'] = code
            self.success = True
        self.set_response({
            'redirect': redirect
        })

    @authorized.role('user')
    def pocket_authorize(self, d):
        '''
        Step 2
        '''
        from services import pocket
        access_token = pocket.get_access_token(self.session.get('pocket_code'))
        if access_token:
            logging.debug(access_token)
            self.user.set_integration_prop('pocket_access_token', access_token)
            self.user.put()
            self.update_session_user(self.user)
            self.success = True
        self.set_response({
            'user': self.user.json() if self.user else None
        })

    @authorized.role('user')
    def pocket_disconnect(self, d):
        '''
        '''
        self.user.set_integration_prop('pocket_access_token', None)
        self.user.put()
        self.update_session_user(self.user)
        self.success = True
        self.set_response({
            'user': self.user.json() if self.user else None
        })


class AgentAPI(handlers.JsonRequestHandler):

    def _get_agent_type(self, body):
        # Facebook Messenger example
        # {u'lang': u'en', u'status': {u'errorType': u'success', u'code': 200}, u'timestamp': u'2017-03-13T14:01:49.275Z', u'sessionId': u'e6d8f9a7-4a70-4049-9214-2c61e88af68d', u'result': {u'parameters': {}, u'contexts': [{u'name': u'generic', u'parameters': {u'facebook_sender_id': u'1182039228580866'}, u'lifespan': 4}], u'resolvedQuery': u'how am i doing?', u'source': u'agent', u'score': 1.0, u'speech': u'', u'fulfillment': {u'messages': [{u'speech': u'Sure, checking', u'type': 0}], u'speech': u'Sure, checking'}, u'actionIncomplete': False, u'action': u'input.status_request', u'metadata': {u'intentId': u'308e5379-7d79-42dd-b66c-7c1d44e1c2fd', u'webhookForSlotFillingUsed': u'false', u'intentName': u'Flow Status Request', u'webhookUsed': u'true'}}, u'id': u'1de76809-1bc3-47f5-ae8e-b7003cdc0f7f', u'originalRequest': {u'source': u'facebook', u'data': {u'timestamp': 1489413704002.0, u'message': {u'text': u'how am i doing?', u'mid': u'mid.1489413704002:027a192309', u'seq': 5398}, u'recipient': {u'id': u'197271657425620'}, u'sender': {u'id': u'1182039228580866'}}}}
        # Google Assistant Example
        # {"id":"dd224f85-cc29-4d27-8100-e5c1a54766c4","timestamp":"2017-03-09T22:19:05.112Z","lang":"en","result":{"source":"agent","resolvedQuery":"GOOGLE_ASSISTANT_WELCOME","speech":"","action":"input.status_request","actionIncomplete":false,"parameters":{},"contexts":[{"name":"google_assistant_welcome","parameters":{},"lifespan":0}],"metadata":{"intentId":"308e5379-7d79-42dd-b66c-7c1d44e1c2fd","webhookUsed":"true","webhookForSlotFillingUsed":"false","intentName":"Genzai Status Request"},"fulfillment":{"speech":"","messages":[]},"score":1.0},"status":{"code":200,"errorType":"success"},"sessionId":"1489097945070","originalRequest":{"source":"google","data":{"surface":{"capabilities":[{"name":"actions.capability.AUDIO_OUTPUT"},{"name":"actions.capability.AUDIO_INPUT"}]},"inputs":[{"arguments":[],"intent":"assistant.intent.action.MAIN","raw_inputs":[{"query":"talk to genzai","input_type":2,"annotation_sets":[]}]}],"user":{"access_token":"KZiPjtEKbyzWTG/o76yWWPsPLdt+kk2i3kkIhkb8mPUMRJds5Tk6QH4HINydK4RN99Lib0X5OPncW7sYb8oAaA5W7VMtnvFaAsMl2VKRGhk=","user_id":"WrBcqMQhQT3X8INoUpiqFZyoALrSlgk4XSmgOTUtjy0="},"device":{},"conversation":{"conversation_id":"1489097945070","type":1}}}}
        from services.agent import AGENT_GOOGLE_ASST, AGENT_FBOOK_MESSENGER
        originalRequest = body.get('originalRequest', {})
        source = originalRequest.get('source')
        if source:
            return {
                'google': AGENT_GOOGLE_ASST,
                'facebook': AGENT_FBOOK_MESSENGER
            }.get(source)

    def _get_user(self, body):
        originalRequest = body.get('originalRequest', {})
        user = originalRequest.get('data', {}).get('user', {})
        access_token = user.get('access_token')
        if access_token:
            user_id = User.user_id_from_aes_access_token(access_token)
            if user_id:
                self.user = User.get_by_id(int(user_id))
        return self.user

    def _get_action_and_params(self, body):
        id = body.get('id')
        logging.debug("Processing agent request with id: %s" % id)
        result = body.get('result', {})
        action = result.get('action')
        parameters = result.get('parameters')
        return (id, action, parameters)

    @authorized.role()
    def apiai_request(self, d):
        '''

        '''
        from secrets import API_AI_AUTH_KEY
        auth_key = self.request.headers.get('Auth-Key')
        res = {'source': 'Flow'}
        speech = None
        data = {}
        if auth_key == API_AI_AUTH_KEY:
            body = tools.getJson(self.request.body)
            logging.debug(body)
            agent_type = self._get_agent_type(body)
            id, action, parameters = self._get_action_and_params(body)
            self._get_user(body)
            from services.agent import ConversationAgent
            ca = ConversationAgent(type=agent_type, user=self.user)
            speech, data = ca.respond_to_action(action, parameters=parameters)

        if not speech:
            speech = "Uh oh, something weird happened"
        res['speech'] = speech
        res['displayText'] = speech
        res['data'] = data
        res['contextOut'] = []
        self.json_out(res, debug=True)

    @authorized.role()
    def fbook_request(self, d):
        '''
        Facebook Messenger request handling
        '''
        from secrets import FB_VERIFY_TOKEN
        verify_token = self.request.get('hub.verify_token')
        hub_challenge = self.request.get('hub.challenge')
        if verify_token and verify_token == FB_VERIFY_TOKEN:
            if hub_challenge:
                self.response.out.write(hub_challenge)
                return

        from services.agent import FacebookAgent
        fa = FacebookAgent(self.request)
        fa.send_response()
        self.success = True
        self.json_out({})