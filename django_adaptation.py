# Identity Map (Innermost Domain)
# ===========================================
# Allocate here business logic and high-level rules that are related to this entity (eg: invariant validations).

class Person:
    def __init__(self, reference, department_id):
        self._reference = reference
        self._department_id = department_id

    @property
    def reference(self):
        return self._reference

    @property
    def department_id(self):
        return self._department_id


# Use Cases Layer (Application Layer)
# ===========================================
# interactors.py contain the business logic of each use case. Place here all the application
# logic. Use command pattern for their implementation because it helps with task enqueueing, rollback when an error
# occurs and also separates dependencies and parameters (really useful for readability, testing and dependency
# injection):

class UseCaseInteractor:
    def __init__(self, person_repo):
        self.person_repo = person_repo

    def set_params(self, reference):
        self.reference = reference
        return self

    def execute(self):
        return self.person_repo.get_person(reference=self.reference)


# Interface Adapters Layer
# ===========================================
# Pieces that are decoupled from framework, but are conscious of the environment
# (API Restful, database storage, caching...).
# First of all we have views.py. They follow Django's view structure but are completely decoupled from it:

class PersonSerializer:
    @staticmethod
    def serialize(person):
        return {
            'reference': person.reference,
            'department_id': person.department_id
        }


class PersonView:
    def __init__(self, get_person_interactor):
        self.get_person_interactor = get_person_interactor

    def get(self, reference):
        try:
            person = (self.get_person_interactor
                      .set_params(reference=reference)
                      .execute())
        except EntityDoesNotExist:
            body = {'error': 'Person does not exist!'}
            status = 404
        else:
            body = PersonSerializer.serialize(person)
            status = 200

        return body, status


class PersonRepo:
    def __init__(self, db_repo, cache_repo):
        self.db_repo = db_repo
        self.cache_repo = cache_repo

    def get_person(self, reference):
        person = self.cache_repo.get_person(reference)

        if person is None:
            person = self.db_repo.get_person(reference)
            self.cache_repo.save_person(person)

        return person


# Framework & Drivers Layer
# ===========================================
# Composed by Django and third party libraries, this layer is also where we place our code related to that parts to
# abstract their implementations (glue code).

class PersonDatabaseRepo:
    def get_person(self, reference):
        try:
            orm_person = ORMPerson.objects.get(reference=reference)
        except ORMPerson.DoesNotExist:
            raise EntityDoesNotExist()

        return self._decode_orm_person(orm_person)

    def _decode_orm_person(self, orm_person):
        return Person(reference=orm_person.reference,
                      department_id=orm_person.department_id)


class ViewWrapper(View):
    view_factory = None

    def get(self, request, *args, **kwargs):
        body, status = self.view_factory.create().get(**kwargs)

        return HttpResponse(json.dumps(body), status=status,
                            content_type='application/json')


# Dependency Injection
# ===========================================
# Factories are in charge of creating and solving dependencies recursively, giving the responsibility of each element
# to its own factory resolver.

class PersonDatabaseRepoFactory:
    @staticmethod
    def get():
        return PersonDatabaseRepo()


class PersonCacheRepoFactory:
    @staticmethod
    def get():
        return PersonCacheRepo()


class PersonRepoFactory:
    @staticmethod
    def get():
        db_repo = PersonDatabaseRepoFactory.get()
        cache_repo = PersonCacheRepoFactory.get()

        return PersonRepo(db_repo, cache_repo)


class GetPersonInteractorFactory:
    @staticmethod
    def get():
        person_repo = PersonRepoFactory.get()

        return UseCaseInteractor(person_repo)


class PersonViewFactory:
    @staticmethod
    def create():
        get_person_interactor = GetPersonInteractorFactory.get()

        return PersonView(get_person_interactor)


url(r'^persons/(?P<reference>\w+)$', ViewWrapper.as_view(view_factory=PersonViewFactory))
