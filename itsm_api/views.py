"""
Implementation for all resources in the API.

This module defines the resources and registers them as view handlers for
flask_restful.

"""

import datetime
import flask
import flask_restful
import json

from flask_accept         import accept
from tinydb               import TinyDB, Query
from tinydb.operations    import delete
from validator_collection import validators

from itsm_api      import app

API = flask_restful.Api(app)    # Initialize the API (managed by flask_restful)
DB  = TinyDB('db.json')         # Initialize our DB 'connection' (provided by TinyDB)

# Pre-create references to our database tables
DB_USER_TABLE               = DB.table('users')
DB_CUSTOMER_TABLE           = DB.table('customers')
DB_USER_CUSTOMER_RELS_TABLE = DB.table('user_customer_rels')
DB_TICKET_TABLE             = DB.table('tickets')
DB_COMMENT_TABLE            = DB.table('comments')

"""
GET  /users/[?<query-string>]
GET  /users/<user-id>
GET  /users/<user-id>/customers
GET  /users/<user-id>/tickets[?<query-string>]
GET  /customers[?<query-string>]
GET  /customers/<cust-id>
GET  /customers/<cust-id>/child-customers[?<query-string>]
GET  /customers/<cust-id>/users/<user-email>
GET  /customers/<cust-id>/tickets[?<query-string>]
GET  /customers/<cust-id>/tickets/<ticket-id>
POST /customers/<cust-id>/tickets
PUT  /tickets/<ticket-id>
GET  /tickets/<ticket-id>/attachments
GET  /tickets/<ticket-id>/attachments/<id>
POST /tickets/<ticket-id>/attachment?name=<attachment-name>
GET  /tickets/<ticket-id>/worknotes/
GET  /tickets/<ticket-id>/worknotes/<id>
POST /tickets/<ticket-id>/worknotes
GET  /tickets/<ticket-id>/comments/
GET  /tickets/<ticket-id>/comments/<id>
POST /tickets/<ticket-id>/comments

"""


def _str_len_check(text, min_len, max_len):
    """
    Validate string type, max and min length.
    """
    if not isinstance(text, str):
        raise ValueError("expected string type")
    if not (min_len <= len(text) <= max_len):
        raise ValueError(f"length should be between {min_len} and {max_len} characters")
    return text


def _dict_sanity_check(data, mandatory_keys, optional_keys, obj=None):
    """
    Perform a sanity check of a dictionary.

    Checks that all mandatory fields are present, and that any other fields are
    part of the specified optional fields. Each key is specified as a tuple: The
    name as well as a validation function, which is called with the key value,
    and which should raise ValueError in case the type/format of the key value
    is not acceptable.

    Returns the dictionary as seen after validation (some validators perform
    light transformation of input values).

    Handling of _created and _updated fields:

    If obj is passed in then the _created field of the object is included in the
    result data, so that this field is not lost when updates are performed. If
    no object is passed in then the _created field is created with the current
    time.

    The _updated field is always going to be set to the current time.

    Raises ValueError if something is wrong.

    """
    # Both mandatory and optional key lists contain tuples, with key name being the first
    # element in each tuple. The validator is not needed for the mandatory / optional key
    # check, so we can ignore it here.
    missing_keys = [k for k, _ in mandatory_keys if k not in data]
    if missing_keys:
        raise ValueError(f"missing mandatory key(s): {', '.join(missing_keys)}")

    # Create a lookup of key name to validator function. The lookup will have an entry for all
    # possible keys, so we can also use it to check if we have any invalid keys.
    keys_to_validators = dict(mandatory_keys + optional_keys)
    always_allowed     = ["id", "_created", "_updated", "_links", "_embedded"]
    invalid_keys = [k for k in data
                    if k not in keys_to_validators and k not in always_allowed]
    if invalid_keys:
        raise ValueError(f"invalid key(s) in request body: {', '.join(invalid_keys)}")

    # Now we individually call the validators on all values in the data, producing a useful
    # error message if possible
    res = {}
    for key, value in data.items():
        try:
            res[key] = keys_to_validators[key](value)
        except ValueError as ex:
            raise ValueError(f"key '{key}': {str(ex)}")

    now_time_string = datetime.datetime.now().isoformat()
    if obj is None:
        res['_created'] = now_time_string
    res['_updated'] = now_time_string
    return res


# ---------------------------------------------------------------
# Parent classes and mixins to help in the rendering of resources
# ---------------------------------------------------------------

class ApiResource:
    """
    Base mixin for a generic API resource.

    Provides the following features:

    - Knows how to get the HTML title for a resource, based on the docstring of
      the resource class.
    - Provides function to render data in nicely formatted HTML.
    - Function to render a clickable link for HTML.
    - Calculate properly formatted URL for a resource.
    - Basic implementations for 'get()' and 'get_html()'.
    - Prepare a _links section for a resource.

    This mixin assumes and uses a '_get()' method, which needs to be implemented
    by any child class.

    """

    URL = "<overwrite in child class>"

    def _get_title_and_explanation(self):
        """
        Extract class docstring to use as title and text in HTML.

        Returns a tuple of title and remaining docstring as explanation.

        """
        title      = ""
        more_lines = []
        if self.__doc__:
            # Find the first non-empty line in the docstring. If there is
            for line in self.__doc__.split("\n")[:-1]:  # strip off last line, always blank
                line = line.strip()
                if line:
                    if not title:
                        # We don't have the title set, yet, so we know this is the first line.
                        if line.endswith("."):
                            # Don't want a period at the end of a title to make it look
                            # better.
                            title = line[:-1]
                        else:
                            title = line
                        continue
                if not line and not more_lines:
                    # We don't need empty lines at the start of the explanation
                    continue
                # Add up the lines of the explanation text
                if line.startswith("*"):
                    line = f"&nbsp; &nbsp; {line}"

                more_lines.append(line or "<br>&nbsp;<br>")  # Empty lines become line break
        return ((title or "A resource"), " ".join(more_lines))

    def _htmlify(self, data):
        """
        Render a resource in nice HTML.
        """
        resource = json.dumps(data, indent=4)
        title, explanation = self._get_title_and_explanation()
        return flask.make_response(
                        flask.render_template('resource.html', title=title,
                                                               explanation=explanation,
                                                               resource=resource),
                        200, {'Content-Type': 'text/html'})

    def _render_link(self, url):
        """
        Render a link either plain or clickable for HTML.
        """
        # The method handlers for the 'text/html' set a flag to indicate that it's to be
        # rendered in a browser. If so, we'll render the link as clickable <a href="...">.
        if self.is_html:
            return f"<a href='{url}'>{url}</a>"
        return url

    def make_links(self, name_url_pairs):
        """
        Create a _links section containing each name/url pair.
        """
        return {name : {"href" : self._render_link(url)}
                for name, url in name_url_pairs.items()}

    @classmethod
    def get_self_url(cls, *args, **kwargs):
        """
        Return resource URL for specific entity.

        Takes the Flask route of the resource and converts it to a format string
        that's then used to render a full URL. The variable elements in the
        route string need to be provided either as positional or keyword args.

        """
        # Convert the route to an f-string type syntax
        route_str = cls.URL.replace("<", "{").replace(">", "}")
        if kwargs:
            # We have keyword arguments. It is assumed that they match the variables
            # defined in the Flask route.
            return route_str.format(**kwargs)
        # We only have args. We need to convert the '{varname}' elements in the string
        # to '{}', in order to use positional parameters in 'format()'.
        new_strs  = []
        remainder = route_str
        while "{" in remainder:
            pre_bracket, tail = route_str.split("{", 1)
            _, remainder      = tail.split("}", 1)
            new_strs.append(pre_bracket + "{}")
        if new_strs:
            new_strs.append(remainder)
            route_str = "".join(new_strs)
        return route_str.format(*args)

    @accept('application/json')
    def get(self, **kwargs):
        """
        Return a resource in plain JSON.
        """
        if not hasattr(self, "_get"):
            flask_restful.abort(405, description=f"Method not allowed")
        self.is_html = False  # pylint: disable=attribute-defined-outside-init
        # We are using kwargs, because the object ID in the URL has different names depending
        # on the resource. The resource _get() implementations therefore use different keyword
        # parameter names, which we don't know here in the base class.
        # _get() is defined in the child class, we don't want pylint to complain, so we allow
        # an exception.
        return self._get(**kwargs)  # pylint: disable=no-member

    @get.support('text/html')
    def get_html(self, **kwargs):
        """
        Return an HTML rendered resource.
        """
        if not hasattr(self, "_get"):
            flask_restful.abort(405, description=f"Method not allowed")
        self.is_html = True  # pylint: disable=attribute-defined-outside-init
        # We are using kwargs, because the object ID in the URL has different names depending
        # on the resource. The resource _get() implementations therefore use different keyword
        # parameter names, which we don't know here in the base class.
        # _get() is defined in the child class, we don't want pylint to complain, so we allow
        # an exception.
        return self._htmlify(self._get(**kwargs))  # pylint: disable=no-member

    @accept('application/json')
    def put(self, **kwargs):
        """
        Return a resource in plain JSON.
        """
        if not hasattr(self, "_put"):
            flask_restful.abort(405, description=f"Method not allowed")
        self.is_html = False  # pylint: disable=attribute-defined-outside-init
        try:
            # We are using kwargs, since in the super class here we don't know the name of the
            # ID parameter (user_id, ticket_id, etc.). The concrete sanity_check() and _put()
            # implementation know. The id parameter name there is matched to the id name
            # specified in the URL.
            kwargs['data'] = flask.request.json
            # self.__class__ at this point will be a child class, which actually implements
            # sanity_check(). We don't want pylint to complain, so allow an exception.
            # pylint: disable=no-member
            kwargs['data'], obj = self.__class__.sanity_check(**kwargs)
            # _put is defined in the child class, only. We don't want pylint to complain, so
            # we allow an exception.
            # pylint: disable=no-member
            _    = self._put(obj=obj, **kwargs)
            resp = flask.make_response({"msg" : "Ok"})
            return resp
        except ValueError as ex:
            flask_restful.abort(400, description=f"Bad Request - {str(ex)}")


class ApiResourceList(ApiResource):
    """
    Base mixin for a generic list of API resources.
    """

    @accept('application/json')
    def post(self):
        """
        Return a resource in plain JSON.
        """
        # Check if this collection resource even implements a POST method
        if not hasattr(self, "_post"):
            flask_restful.abort(405, description=f"Method not allowed")
        self.is_html = False  # pylint: disable=attribute-defined-outside-init
        try:
            # _post() and SINGLE_RESOURCE_CLASS are defined in a child class, only. We don't
            # want pylint to complain about those, so we allow exceptions.
            # Perform a sanity check and produce a cleaned version of the input
            # pylint: disable=no-member
            data, _ = self.SINGLE_RESOURCE_CLASS.sanity_check(flask.request.json)
            # pylint: disable=no-member
            new_url = self._post(data)
            resp    = flask.make_response({"msg" : "Ok", "location" : new_url}, 201)
            resp.headers.extend({"Location" : new_url})
            return resp
        except ValueError as ex:
            flask_restful.abort(400, description=f"Bad Request - {str(ex)}")


# -------------------------------
# The actual resources in our API
# -------------------------------

class Root(flask_restful.Resource, ApiResource):
    """
    The root resource, with links to other resources in the API.

    In any resource, look for a `_links` element. It contains references to
    additional or related resources. It also always contains a link to `self`,
    so that it is always clear how we found this resource. For some resources
    there also is a `contained_in` link, which refers to the collection or other
    parent of the current resource.

    """

    URL   = "/"

    def _get(self):
        """
        Return the root resource, which includes links to all collections.
        """
        return {
            "_links" : self.make_links({
                "self"                       : Root.get_self_url(),
                "users"                      : UserList.get_self_url(),
                "customers"                  : CustomerList.get_self_url(),
                "tickets"                    : TicketList.get_self_url(),
                "comments"                   : CommentList.get_self_url(),
                "customer_user_associations" : CustomerUserAssociationList.get_self_url(),
            })
        }


class _UserDataEmbedder:
    """
    A mixin that provides a function to embed a user list in a result.
    """

    def embed_user_data_in_result(self, user_data):
        res = []
        for user in user_data:
            d = {
                    "id"       : user.doc_id,
                    "email"    : user['email'],
                    "_created" : user.get('_created', ''),
                    # make_links is provided by the class using this mixin
                    # pylint: disable=no-member
                    "_links"   : self.make_links({"self" : User.get_self_url(user.doc_id)})
            }
            if '_updated' in user:
                d['_updated'] = user['_updated']
            res.append(d)
        return res


class UserList(flask_restful.Resource, ApiResourceList, _UserDataEmbedder):
    """
    A list of users.

    This is a collection with 'embedded' information. This means some
    information about the individual users is included here to provide a quick
    access to the most important information without having to load the full
    user resource through an additional request.

    To see all the details of a user, follow the 'self' link to the user
    resource.

    """

    URL   = "/users"

    def _get(self):
        """
        Return the user table data.
        """
        user_data = DB_USER_TABLE.all()

        res = {
            "total_queried" : len(user_data),
            "_embedded" : {
                "users" : self.embed_user_data_in_result(user_data)
            },
            "_links" : self.make_links({
                           "self" :         UserList.get_self_url(),
                           "contained_in" : Root.get_self_url()
                       })
        }
        return res

    def _post(self, data):
        """
        Process a POST to create a new user.

        This may raise exceptions in case of malformed input data.

        """
        new_user_id = DB_USER_TABLE.insert(data)
        return User.get_self_url(user_id=new_user_id)


class User(flask_restful.Resource, ApiResource):
    """
    An individual user.

    A "user" is a person, which is associated with one or more "customers"
    (clients of a service provider). Typically, this is someone working for the
    customer organization and who may contact the service desk to raise a
    ticket.

    The only mandatory field in a user resource is the `id` field as well as a
    list of one or more email addresses.

    Additional fields may be available or configured by the ITSM backend, but
    they always are represented under `custom_fields` as key value pairs. This
    may include other fields that are mandatory within the ITSM backend.

    Note that in the `_links` section you can find a reference to all the
    tickets that were created by this user, as well as a list to all the
    customers that this user is associated with.

    """

    URL = UserList.URL + "/<user_id>"

    @classmethod
    def exists(cls, user_id):
        """
        Validate to ensure that a specified user exists.
        """
        user_id = int(user_id)
        user    = DB_USER_TABLE.get(doc_id=user_id)
        if not user:
            raise ValueError(f"unknown user '{user_id}'")
        return user_id

    def _get(self, user_id):
        """
        Return information about a single user.
        """
        user = DB_USER_TABLE.get(doc_id=int(user_id))
        if not user:
            flask_restful.abort(404, message=f"User '{user_id}' not found!")
        res = {
            "id" : user.doc_id
        }
        res.update(user)
        res['_links'] = self.make_links({
                            "self" :         User.get_self_url(user.doc_id),
                            "contained_in" : UserList.get_self_url(),
                            "customers" :    UserCustomerList.get_self_url(user.doc_id),
                            "tickets" :      UserTicketList.get_self_url(user.doc_id)
                        })
        return res

    @classmethod
    def sanity_check(cls, data, user_id=None):
        """
        Perform sanity check for POST/PUT user data.
        """
        if user_id is not None:
            user_id = int(user_id)
            user    = DB_USER_TABLE.get(doc_id=user_id)
            if not user:
                flask_restful.abort(404, message=f"user '{user_id}' not found!")
        else:
            user = None

        # Create a custom validator to successully validate the emails in the context of this
        # user, so that we can allow an update to the specified user with existing emails, but
        # disallow it if some other user has the specified emails. This function captures the
        # current user ID as it is a closure.
        def validate_emails(email_list):
            if not isinstance(email_list, list):
                raise ValueError("email needs to be a list")
            ret = []
            for e in email_list:
                # raises exception if malformed email
                validators.email(e)
                # check if any user has this email already
                UserQuery = Query()
                user_set_similar_email = DB_USER_TABLE.search(UserQuery.email.any(e))
                for user in user_set_similar_email:
                    if user_id is not None and (str(user.doc_id) == str(user_id)):
                        # We will match ourselves if some emails are still the same, but
                        # that's ok, so skip this check
                        continue
                    for email in user['email']:
                        if e == email:
                            raise ValueError(f"user with email '{email}' exists already")
                ret.append(e)
            return ret

        # Perform some sanity checking of the provided attributes
        data = _dict_sanity_check(data,
                                  mandatory_keys = [("email", validate_emails)],
                                  optional_keys = [("custom_fields", dict)],
                                  obj=user)
        return data, user

    def _put(self, data, user_id, obj):
        """
        Process a PUT to update an existing user.

        This may raise exceptions in case of malformed input data.

        """
        user    = obj
        user_id = int(user_id)
        # Find all the keys that we should remove from the stored representation, due to them
        # not being what's been PUT to us.
        keys_to_remove = [stored_key for stored_key in user.keys()
                          if stored_key not in data]
        for old_key in keys_to_remove:
            DB_USER_TABLE.update(delete(old_key), doc_ids=[user_id])
        DB_USER_TABLE.update(data, doc_ids=[user_id])
        return User.get_self_url(user_id=user_id)


class _CustomerDataEmbedder:
    """
    A mixin that provides a function to embed a customer list in a result.
    """

    def embed_customer_data_in_result(self, cust_data):
        res = []
        for cust in cust_data:
            d = {
                    "id"       : cust.doc_id,
                    "name"     : cust['name'],
                    "_created" : cust.get('_created', ''),
                    # make_links is provided by the class using this mixin
                    # pylint: disable=no-member
                    "_links"   : self.make_links({
                                     "self" : Customer.get_self_url(cust.doc_id)}
                                 )
            }
            if '_updated' in cust:
                d['_updated'] = cust['_updated']
            res.append(d)
        return res


class UserCustomerList(flask_restful.Resource, ApiResourceList, _CustomerDataEmbedder):
    """
    List of customers for a given user.

    This is a collection with 'embedded' information. This means some
    information about the individual customers is included here to provide a
    quick access to the most important information without having to load the
    full customer resource through an additional request.

    To see all the details of a customer, follow the 'self' link to the customer
    resource.

    """

    URL = User.URL + "/customers/"

    def _get(self, user_id):
        """
        Return the customer list for a given user.
        """
        rels_q       = Query()
        rel_data     = DB_USER_CUSTOMER_RELS_TABLE.search(rels_q.user_id == int(user_id))
        customer_ids = [r['customer_id'] for r in rel_data]
        # We don't seem to have a way to retrieve a set of objects via a set of ids?
        # Doing it just in a loop for now...
        cust_data    = [DB_CUSTOMER_TABLE.get(doc_id=_id) for _id in customer_ids]

        res = {
            "total_queried" : len(cust_data),
            "_embedded"     : {
                "customers" : self.embed_customer_data_in_result(cust_data)
            },
            "_links"        : self.make_links({
                                  "self"         : UserCustomerList.get_self_url(user_id),
                                  "contained_in" : User.get_self_url(user_id)
                              })
        }
        return res


class CustomerUserAssociationList(flask_restful.Resource, ApiResourceList):
    """
    A collection resource to manage the association of users to customers.

    This resource is not 'user friendly' to the extend that it does not contain
    embedded resources. Instead, it is merely used to cleanly and RESTfully
    express the association of users to customers. These associations can be
    created or deleted here.

    The User and Customer resources provide more user friendly means to read
    which customer a user belongs to or which users a customer has.

    """

    URL = "/customer_user_associations"

    def _get(self):
        """
        Return the list of associations.
        """
        associations = DB_USER_CUSTOMER_RELS_TABLE.all()
        for association in associations:
            association['_links'] = self.make_links({
                'self' : CustomerUserAssociation.get_self_url(association.doc_id)
            })
        res = {
            "total_queried" : len(associations),
            "associations"  : associations,
            "_links" : self.make_links({
                           "self"         : CustomerUserAssociationList.get_self_url(),
                           "contained_in" : Root.get_self_url()
                       })
        }
        return res

    def _post(self, data):
        """
        Process the addition of a user/customer association.

        The request body for this consists of a JSON dictionary, with an entry
        like this:

            {
                "user_id"     : "<user_id>",
                "customer_id" : "<customer_id>"
            }

        """
        cust_id = data['customer_id']
        user_id = data['user_id']

        # Now check if we have this association already
        assoc_q    = Query()
        assoc_data = DB_USER_CUSTOMER_RELS_TABLE.search((assoc_q.customer_id == cust_id) &
                                                        (assoc_q.user_id     == user_id))
        if assoc_data:
            flask_restful.abort(400, message="Bad Request - Assocation between customer "
                                             "and user exists already.")

        new_association_id = DB_USER_CUSTOMER_RELS_TABLE.insert(data)
        return CustomerUserAssociation.get_self_url(association_id=new_association_id)


class CustomerUserAssociation(flask_restful.Resource, ApiResource,
                              _UserDataEmbedder, _CustomerDataEmbedder):
    """
    A resource to represent the association between customer and user.
    """

    URL = CustomerUserAssociationList.URL + "/<association_id>"

    @classmethod
    def sanity_check(cls, data):  # no version with ID, since PUT (update) isn't allowed
        """
        Perform sanity check for POST customer/user association data.
        """
        data = _dict_sanity_check(data,
                                  mandatory_keys = [
                                      ("user_id", User.exists),
                                      ("customer_id", Customer.exists)
                                  ],
                                  optional_keys = [])
        return data, None

    def _get(self, association_id):
        """
        Return the information about a customer/user association.
        """
        association = DB_USER_CUSTOMER_RELS_TABLE.get(doc_id=int(association_id))
        if not association:
            flask_restful.abort(404, message=f"Customer/user association '{association_id}' "
                                              "not found!")
        res = {
            "id" : association.doc_id
        }
        res.update(association)
        cust_data = [DB_CUSTOMER_TABLE.get(doc_id=association['customer_id'])]
        user_data = [DB_USER_TABLE.get(doc_id=association['user_id'])]
        res['_embedded'] = {
            "user"     : self.embed_user_data_in_result(user_data),
            "customer" : self.embed_customer_data_in_result(cust_data)
        }
        link_spec = {
            "self"         : CustomerUserAssociation.get_self_url(association.doc_id),
            "contained_in" : CustomerUserAssociationList.get_self_url()
        }

        res['_links'] = self.make_links(link_spec)
        return res


class CustomerList(flask_restful.Resource, ApiResourceList, _CustomerDataEmbedder):
    """
    A list of customers.

    This is a collection with 'embedded' information. This means some
    information about the individual customers is included here to provide a
    quick access to the most important information without having to load the
    full customer resource through an additional request.

    To see all the details of a customer, follow the 'self' link to the customer
    resource.

    """

    URL = "/customers"

    def _get(self):
        """
        Return the customer list.
        """
        cust_data = DB_CUSTOMER_TABLE.all()

        res = {
            "total_queried" : len(cust_data),
            "_embedded"     : {
                "customers" : self.embed_customer_data_in_result(cust_data)
            },
            "_links"        : self.make_links({
                                  "self" :         CustomerList.get_self_url(),
                                  "contained_in" : Root.get_self_url(),
                              })
        }
        return res


class Customer(flask_restful.Resource, ApiResource):
    """
    An individual customer.

    A "customer" is a commercial client of the service provider. It typically
    has users associated with it, which may contact the service desk to raise
    tickets.

    The only mandatory fields in a customer resource are the `id` field and a
    name.

    Additional fields may be available or configured by the ITSM backend, but
    they always are represented under `custom_fields` as key value pairs. This
    may include other fields that are mandatory within the ITSM backend.

    """

    URL = CustomerList.URL + "/<customer_id>"

    @classmethod
    def exists(cls, customer_id):
        """
        Validate to ensure that a specified customer exists.
        """
        customer_id = int(customer_id)
        cust        = DB_CUSTOMER_TABLE.get(doc_id=customer_id)
        if not cust:
            raise ValueError(f"unknown customer '{customer_id}'")
        return customer_id

    def _get(self, customer_id):
        """
        Return information about a single customer.
        """
        cust = DB_CUSTOMER_TABLE.get(doc_id=int(customer_id))
        if not cust:
            flask_restful.abort(404, message=f"Customer '{customer_id}' not found!")
        res = {
            "id" : cust.doc_id
        }
        res.update(cust)
        link_spec = {
            "self" :         Customer.get_self_url(cust.doc_id),
            "contained_in" : CustomerList.get_self_url(),
            "users" :        CustomerUserList.get_self_url(cust.doc_id),
            "tickets" :      CustomerTicketList.get_self_url(cust.doc_id)
        }

        # A customer may have a parent customer
        parent_id = cust.get('parent_id')
        if parent_id is not None:
            link_spec['parent'] = Customer.get_self_url(parent_id)

        res['_links'] = self.make_links(link_spec)
        return res


class CustomerUserList(flask_restful.Resource, ApiResourceList, _UserDataEmbedder):
    """
    List of users for a given customer.

    This is a collection with 'embedded' information. This means some
    information about the individual users is included here to provide a
    quick access to the most important information without having to load the
    full user resource through an additional request.

    To see all the details of a user, follow the 'self' link to the user
    resource.

    """

    URL = Customer.URL + "/users/"

    def _get(self, customer_id):
        """
        Return list of users for a customer.
        """
        cust = DB_CUSTOMER_TABLE.get(doc_id=int(customer_id))
        if not cust:
            flask_restful.abort(404, message=f"Customer '{customer_id}' not found!")
        rels_q    = Query()
        rel_data  = DB_USER_CUSTOMER_RELS_TABLE.search(rels_q.customer_id == int(customer_id))
        user_ids  = [r['user_id'] for r in rel_data]
        # We don't seem to have a way to retrieve a set of objects via a set of ids?
        # Doing it just in a loop for now...
        user_data = [DB_USER_TABLE.get(doc_id=_id) for _id in user_ids]

        res = {
            "total_queried" : len(user_data),
            "_embedded"     : {
                "users" : self.embed_user_data_in_result(user_data)
            },
            "_links"        : self.make_links({
                                  "self"         : CustomerUserList.get_self_url(customer_id),
                                  "contained_in" : Customer.get_self_url(customer_id)
                              })
        }
        return res


class _TicketDataEmbedder:
    """
    A mixin that provides a function to embed a ticket list in a result.
    """

    def embed_ticket_data_in_result(self, ticket_data):
        res = []
        for ticket in ticket_data:
            d = {
                    "id"             : ticket.doc_id,
                    "aportio_id"     : ticket['aportio_id'],
                    "customer_id"    : ticket['customer_id'],
                    "short_title"    : ticket['short_title'],
                    "_created"       : ticket.get('_created', ''),
                    "status"         : ticket['status'],
                    "classification" : ticket['classification'].get("l1", "(none)"),
                    # make_links is provided by the class using this mixin
                    # pylint: disable=no-member
                    "_links"         : self.make_links({
                                           "self" : Ticket.get_self_url(ticket.doc_id)
                                       })
            }
            if '_updated' in ticket:
                d['_updated'] = ticket['_updated']
            res.append(d)
        return res


class CustomerTicketList(flask_restful.Resource, ApiResourceList, _TicketDataEmbedder):
    """
    A list of tickets of a customers.

    This is a collection with 'embedded' information. This means some
    information about the individual tickets is included here to provide a
    quick access to the most important information without having to load the
    full ticket resource through an additional request.

    To see all the details of a ticket, follow the 'self' link to the ticket
    resource.

    """

    URL = "/customers/<customer_id>/tickets"

    def _get(self, customer_id):
        """
        Return list of tickets for a customer.
        """
        ticket_q    = Query()
        ticket_data = DB_TICKET_TABLE.search(ticket_q.customer_id == int(customer_id))

        res = {
            "total_queried" : len(ticket_data),
            "_embedded"     : {
                "tickets" : self.embed_ticket_data_in_result(ticket_data)
            },
            "_links" : self.make_links({
                           "self" :         CustomerTicketList.get_self_url(customer_id),
                           "contained_in" : Customer.get_self_url(customer_id)
                       })
        }
        return res


class UserTicketList(flask_restful.Resource, ApiResourceList, _TicketDataEmbedder):
    """
    A list of tickets of a user.

    This is a collection with 'embedded' information. This means some
    information about the individual tickets is included here to provide a
    quick access to the most important information without having to load the
    full ticket resource through an additional request.

    To see all the details of a ticket, follow the 'self' link to the ticket
    resource.

    """

    URL = "/users/<user_id>/tickets"

    def _get(self, user_id):
        """
        Return the ticket list of a user.
        """
        ticket_q    = Query()
        ticket_data = DB_TICKET_TABLE.search(ticket_q.user_id == int(user_id))

        res = {
            "total_queried" : len(ticket_data),
            "_embedded"     : {
                "tickets" : self.embed_ticket_data_in_result(ticket_data)
            },
            "_links" : self.make_links({
                           "self" :         UserTicketList.get_self_url(user_id),
                           "contained_in" : User.get_self_url(user_id)
                       })
        }
        return res


class TicketList(flask_restful.Resource, ApiResourceList, _TicketDataEmbedder):
    """
    The list of tickets.

    This is a collection with 'embedded' information. This means some
    information about the individual tickets is included here to provide a
    quick access to the most important information without having to load the
    full ticket resource through an additional request.

    To see all the details of a ticket, follow the 'self' link to the ticket
    resource.

    """

    URL = "/tickets"

    def _get(self):
        """
        Return the ticket table data.
        """
        ticket_data = DB_TICKET_TABLE.all()

        res = {
            "total_queried" : len(ticket_data),
            "_embedded"     : {
                "tickets" : self.embed_ticket_data_in_result(ticket_data)
            },
            "_links" : self.make_links({
                           "self" :         TicketList.get_self_url(),
                           "contained_in" : Root.get_self_url()
                       })
        }
        return res

    def _post(self, data):
        """
        Process the addition of a ticket.
        """
        new_ticket_id = DB_TICKET_TABLE.insert(data)
        return Ticket.get_self_url(ticket_id=new_ticket_id)


class _CommentDataEmbedder:
    """
    A mixin that provides a function to embed a comment list in a result.
    """

    def embed_comment_data_in_result(self, comment_data):
        res = []
        for comment in comment_data:
            d = {
                "id"       : comment.doc_id,
                "user_id"  : comment['user_id'],
                "text"     : comment['text'],
                "_created" : comment.get('_created', ''),
                # pylint: disable=no-member
                "_links"   : self.make_links({"self" : Comment.get_self_url(comment.doc_id)})
            }
            if "_updated" in comment:
                d['_updated'] = comment['_updated']
            res.append(d)
        return res


class Ticket(flask_restful.Resource, ApiResource, _CommentDataEmbedder):
    """
    An individual service desk ticket.

    A "ticket" represents a service desk ticket that has been created within
    the ITSM backend by a user.

    A ticket has a number of attributes:

    * aportio_id: This is an internal ticket ID that has been created by
    Aportio's system. While the attribute itself is not mandatory, we strongly
    recommend that this value is stored in the ITSM, possibly via an ITSM
    custom field.

    * customer_id: The customer against which this ticket was filed.

    * short_title: The headline of the ticket. This may be the email's subject
      line, for example.

    * long_text: The cleaned, non-HTML text of the ticket description.

    * user_id: The ID of the user that created the ticket.

    * status: The current status of the ticket. Permissible values are: OPEN
      CLOSED, etc.

    * created: The date/time when the ticket was created.

    * classification: A dictionary with L1 and possibly also L2 and L3
      classification outcomes for this ticket, as provided by Aportio.

    In addition, ITSM/customer specific custom fields may be present.

    A ticket may also contain additional entries for lists of worknotes and
    comments. Each of those has the same format:

    * id: A unique ID or index within the ticket.

    * user_id: The ID of the user that created the worknote/comment.

    * created: The date/time when the worknote/comment was created.

    * text: The actual content of the worknote/comment.

    Note that the `_links` section may contain links to attachments of this
    ticket.

    """

    URL                 = TicketList.URL + "/<ticket_id>"
    SHORT_TITLE_MIN_LEN = 2
    SHORT_TITLE_MAX_LEN = 300
    LONG_TEXT_MIN_LEN   = 0
    LONG_TEXT_MAX_LEN   = 25000000

    @classmethod
    def exists(cls, ticket_id):
        """
        Validate to ensure that a specified ticket exists.
        """
        ticket_id = int(ticket_id)
        ticket    = DB_TICKET_TABLE.get(doc_id=ticket_id)
        if not ticket:
            raise ValueError(f"unknown ticket '{ticket_id}'")
        return ticket_id

    def _get(self, ticket_id):
        """
        Return information about a ticket.
        """
        ticket_id = int(ticket_id)
        ticket    = DB_TICKET_TABLE.get(doc_id=ticket_id)
        if not ticket:
            flask_restful.abort(404, message=f"Ticket '{ticket_id}' not found!")
        comments_q = Query()
        comments   = DB_COMMENT_TABLE.search((comments_q.ticket_id == ticket_id) &
                                             (comments_q.type      == Comment.TYPE_COMMENT))
        worknotes  = DB_COMMENT_TABLE.search((comments_q.ticket_id == ticket_id) &
                                             (comments_q.type      == Comment.TYPE_WORKNOTE))
        res = {
            "id" : ticket.doc_id,
        }
        res.update(ticket)
        res['_embedded'] = {
            "comments" : self.embed_comment_data_in_result(comments),
            "worknotes" : self.embed_comment_data_in_result(worknotes)
        }
        res['_links'] = self.make_links({
                            "self" :         Ticket.get_self_url(ticket.doc_id),
                            "contained_in" : TicketList.get_self_url(),
                            "customer" :     Customer.get_self_url(res['customer_id']),
                            "user" :         User.get_self_url(res['user_id'])
                        })
        return res

    @classmethod
    def valid_status(cls, status_str):
        """
        Validate to confirm that the specified status value is valid.
        """
        status_str = status_str.upper()
        if status_str not in ["OPEN", "CLOSED"]:
            raise ValueError(f"invalid ticket status '{status_str}'")
        return status_str

    @classmethod
    def valid_classification(cls, classification_dict):
        """
        Validate to confirm that the specified classification dict is valid.

        The classification dictionary has a mandatory entry "l1", and then the
        possible additional values "l2" and "l3".

        """
        invalid_keys = [k for k, _ in classification_dict if k not in ["l1", "l2", "l3"]]
        if invalid_keys:
            raise ValueError(f"invalid key(s) in classification: {', '.join(invalid_keys)}")

        if classification_dict and "l1" not in classification_dict:
            raise ValueError("L1 classification missing")

        return classification_dict

    @classmethod
    def sanity_check(cls, data, ticket_id=None):
        """
        Perform sanity check for POST/PUT ticket data.

        If a ticket ID was specified, this also looks up the object in the DB
        and returns this object.

        Return value is a tuple, consisting of cleaned and verified request data
        as well as an object (or None).

        """
        if ticket_id is not None:
            ticket_id = int(ticket_id)
            ticket    = DB_TICKET_TABLE.get(doc_id=ticket_id)
            if not ticket:
                flask_restful.abort(404, message=f"ticket '{ticket_id}' not found!")
        else:
            ticket = None

        # A custom validator to make sure the aportio ID remains unique
        def validate_aportio_id(aportio_id):
            if not isinstance(aportio_id, str):
                raise ValueError("expected string type for aportio ID")
            TicketQuery = Query()
            ticket_with_aportio_id = DB_TICKET_TABLE.get(
                                                    TicketQuery.aportio_id == aportio_id)
            if ticket_with_aportio_id and (ticket_with_aportio_id.doc_id != ticket_id):
                raise ValueError(f"a ticket with aportio ID '{aportio_id}' "
                                 f"exists already")
            return aportio_id

        # A custom validator for the short title
        def validate_short_title(text):
            return _str_len_check(text, cls.SHORT_TITLE_MIN_LEN, cls.SHORT_TITLE_MAX_LEN)

        # A custom validator for the long text
        def validate_long_text(text):
            return _str_len_check(text, cls.LONG_TEXT_MIN_LEN, cls.LONG_TEXT_MAX_LEN)

        # Perform some sanity checking of the provided attributes
        data = _dict_sanity_check(data,
                                  mandatory_keys = [
                                      ("aportio_id", validate_aportio_id),
                                      ("customer_id", Customer.exists),
                                      ("short_title", validate_short_title),
                                      ("user_id", User.exists),
                                      ("status", Ticket.valid_status),
                                      ("classification", Ticket.valid_classification)],
                                  optional_keys = [
                                      ("long_text", validate_long_text),
                                      ("custom_fields", dict)],
                                  obj=ticket)
        # Now check whether this user is even associated with that customer
        cust_id    = data['customer_id']
        user_id    = data['user_id']
        assoc_q    = Query()
        assoc_data = DB_USER_CUSTOMER_RELS_TABLE.search((assoc_q.customer_id == cust_id) &
                                                        (assoc_q.user_id     == user_id))
        if not assoc_data:
            flask_restful.abort(400, message=f"Bad Request - User '{user_id}' is not "
                                             f"associated with customer '{cust_id}'")
        return data, ticket

    def _put(self, data, ticket_id, obj):
        """
        Process a PUT update to an ticket comment.
        """
        ticket    = obj
        ticket_id = int(ticket_id)

        # Ensure that user and customer have not been changed (they can only be written once)
        if data['user_id'] != ticket['user_id']:
            flask_restful.abort(400, message=f"Bad Request - Cannot change user ID in "
                                             f"ticket '{ticket_id}'")
        if data['customer_id'] != ticket['customer_id']:
            flask_restful.abort(400, message=f"Bad Request - Cannot change customer ID in "
                                             f"ticket '{ticket_id}'")

        # Remove keys that are not in the new resource
        keys_to_remove = [stored_key for stored_key in ticket.keys()
                          if stored_key not in data]
        for old_key in keys_to_remove:
            DB_TICKET_TABLE.update(delete(old_key), doc_ids=[ticket_id])
        DB_TICKET_TABLE.update(data, doc_ids=[ticket_id])
        return Ticket.get_self_url(ticket_id=ticket_id)


class CommentList(flask_restful.Resource, ApiResourceList):
    """
    A list of comments (either public or private).

    This resource is not 'user friendly' to the extend that it does not contain
    embedded resources. Instead, it is merely used to cleanly and RESTfully
    express the association of comments to tickets as well as the contents of
    those comments.

    The Ticket resource provides more user friendly means to read the comments
    and worknotes associated with that ticket, by displaying those as embedded
    resources, where the embedded information in fact shows all information
    about the comment/worknote.

    """

    URL = "/comments"

    def _get(self):
        """
        Return the list of all comments/worknotes.
        """
        comments = DB_COMMENT_TABLE.all()
        for comment in comments:
            comment['_links'] = self.make_links({
                'self' : Comment.get_self_url(comment.doc_id)
            })
        res = {
            "total_queried" : len(comments),
            "comments"      : comments,
            "_links" : self.make_links({
                           "self"         : CommentList.get_self_url(),
                           "contained_in" : Root.get_self_url()
                       })
        }
        return res

    def _post(self, data):
        """
        Process the addition of a comment to a ticket.
        """
        new_comment_id = DB_COMMENT_TABLE.insert(data)
        return Comment.get_self_url(comment_id=new_comment_id)


class Comment(flask_restful.Resource, ApiResource,
              _TicketDataEmbedder, _UserDataEmbedder, _CustomerDataEmbedder):
    """
    A resource to represent a comment/worknote.
    """

    URL           = CommentList.URL + "/<comment_id>"
    MIN_LEN       = 2
    MAX_LEN       = 25000000   # allowing for really big comments!
    TYPE_COMMENT  = "COMMENT"
    TYPE_WORKNOTE = "WORKNOTE"
    KNOWN_TYPES   = [TYPE_COMMENT, TYPE_WORKNOTE]

    @classmethod
    def exists(cls, comment_id):
        """
        Validate to ensure that a specified comment exists.
        """
        comment_id = int(comment_id)
        comment    = DB_COMMENT_TABLE.get(doc_id=comment_id)
        if not comment:
            raise ValueError(f"unknown comment '{comment_id}'")
        return comment_id

    def _get(self, comment_id):
        """
        Return information about a single comment.
        """
        comment = DB_COMMENT_TABLE.get(doc_id=int(comment_id))
        if not comment:
            flask_restful.abort(404, message=f"Comment '{comment_id}' not found!")
        ticket_data   = DB_TICKET_TABLE.get(doc_id=comment['ticket_id'])
        customer_data = DB_CUSTOMER_TABLE.get(doc_id=ticket_data['customer_id'])
        user_data     = DB_USER_TABLE.get(doc_id=comment['user_id'])
        res = dict(comment)
        res.update({
            "id" : comment.doc_id,
            "_embedded" : {
                "ticket"   : self.embed_ticket_data_in_result([ticket_data])[0],
                "user"     : self.embed_user_data_in_result([user_data])[0],
                "customer" : self.embed_customer_data_in_result([customer_data])[0]
            },
            '_links' : self.make_links({
                           "self" :         Comment.get_self_url(comment.doc_id),
                           "contained_in" : CommentList.get_self_url(),
                       })
        })
        return res

    @classmethod
    def sanity_check(cls, data, comment_id=None):
        """
        Perform a sanity check for POST/PUT of comment data.
        """
        if comment_id is not None:
            comment_id = int(comment_id)
            comment    = DB_COMMENT_TABLE.get(doc_id=comment_id)
            if not comment:
                flask_restful.abort(404, message=f"comment '{comment_id}' not found!")
        else:
            comment = None

        def validate_str(text):
            return _str_len_check(text, cls.MIN_LEN, cls.MAX_LEN)

        def validate_type(text):
            text = text.upper()
            if text not in cls.KNOWN_TYPES:
                raise ValueError(f"unknown comment type '{text}'")
            return text

        data = _dict_sanity_check(data,
                                  mandatory_keys = [
                                      ("user_id", User.exists),
                                      ("ticket_id", Ticket.exists),
                                      ("text", validate_str),
                                      ("type", validate_type)],
                                  optional_keys = [],
                                  obj=comment)
        # Check that the user is associated with the customer of the ticket.
        ticket     = DB_TICKET_TABLE.get(doc_id=data['ticket_id'])
        cust_id    = ticket['customer_id']
        user_id    = data['user_id']
        assoc_q    = Query()
        assoc_data = DB_USER_CUSTOMER_RELS_TABLE.search((assoc_q.customer_id == cust_id) &
                                                        (assoc_q.user_id     == user_id))
        if not assoc_data:
            flask_restful.abort(400, message=f"Bad Request - User '{user_id}' is not "
                                             f"associated with ticket customer '{cust_id}'")
        if comment_id is None:
            data['_created'] = datetime.datetime.now().isoformat()
        else:
            data['_updated'] = datetime.datetime.now().isoformat()

        return data, comment

    def _put(self, data, comment_id, obj):
        """
        Process a PUT update to an existing comment.
        """
        comment    = obj
        comment_id = int(comment_id)

        # Ensure that user and customer have not been changed (they can only be written once)
        if data['user_id'] != comment['user_id']:
            flask_restful.abort(400, message=f"Bad Request - Cannot change user ID in "
                                             f"comment '{comment_id}'")
        if data['customer_id'] != comment['customer_id']:
            flask_restful.abort(400, message=f"Bad Request - Cannot change customer ID in "
                                             f"comment '{comment_id}'")

        # Remove keys that are not in the new resource
        keys_to_remove = [stored_key for stored_key in comment.keys()
                          if stored_key not in data]
        for old_key in keys_to_remove:
            DB_COMMENT_TABLE.update(delete(old_key), doc_ids=[comment_id])
        DB_COMMENT_TABLE.update(data, doc_ids=[comment_id])
        return Comment.get_self_url(comment_id=comment_id)


# ------------------------------------------------------------------------------------------
# Now that all resources (collections and singles) are defined, we can let the collection
# know - via class attribute - which class implements the single resource of the collection.
# Couldn't do this while we defined the class, since there's no forward declaration in
# Python.
# ------------------------------------------------------------------------------------------
UserList.SINGLE_RESOURCE_CLASS                    = User
CustomerList.SINGLE_RESOURCE_CLASS                = Customer
CustomerUserAssociationList.SINGLE_RESOURCE_CLASS = CustomerUserAssociation
TicketList.SINGLE_RESOURCE_CLASS                  = Ticket
CommentList.SINGLE_RESOURCE_CLASS                 = Comment

# ----------------------------------------------------
# Registering the resource classes with our Flask app.
# ----------------------------------------------------
for resource_class in [Root,
                       UserList, User, UserCustomerList, UserTicketList,
                       Customer, CustomerList, CustomerUserList, CustomerTicketList,
                       CustomerUserAssociationList, CustomerUserAssociation,
                       Ticket, TicketList, Comment, CommentList]:
    API.add_resource(resource_class, resource_class.URL)
