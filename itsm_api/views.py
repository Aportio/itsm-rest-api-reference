"""
Implementation for all resources in the API.

This module defines the resources and registers them as view handlers for
flask_restful.

"""

import json
import flask
import flask_restful

from flask_accept  import accept
from tinydb        import TinyDB, Query

from itsm_api      import app

API = flask_restful.Api(app)    # Initialize the API (managed by flask_restful)
DB  = TinyDB('db.json')         # Initialize our DB 'connection' (provided by TinyDB)

# Pre-create references to our database tables
DB_USER_TABLE               = DB.table('users')
DB_CUSTOMER_TABLE           = DB.table('customers')
DB_USER_CUSTOMER_RELS_TABLE = DB.table('user_customer_rels')
DB_TICKET_TABLE             = DB.table('tickets')

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

    def _get_title(self):
        """
        Extract first line of class docstring to use as title in HTML.
        """
        title = "A resource"  # default if there is no docstring
        if self.__doc__:
            # Find the first non-empty line in the docstring. If there is
            for line in self.__doc__.split("\n"):
                line = line.strip()
                if line:
                    if line.endswith("."):
                        # Don't want a period at the end of a title to make it look better.
                        title = line[:-1]
                    else:
                        title = line
                    break
        return title

    def _htmlify(self, data):
        """
        Render a resource in nice HTML.
        """
        resource = json.dumps(data, indent=4)
        return flask.make_response(
                        flask.render_template('resource.html', title=self._get_title(),
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

    def _get(self, *args, **kwargs):
        """
        Return the raw data for the resource.
        """
        raise NotImplementedError("needs to be implemented by child class")

    @accept('application/json')
    def get(self, *args, **kwargs):
        """
        Return a resource in plain JSON.
        """
        self.is_html = False  # pylint: disable=attribute-defined-outside-init
        return self._get(*args, **kwargs)

    @get.support('text/html')
    def get_html(self, *args, **kwargs):
        """
        Return an HTML rendered resource.
        """
        self.is_html = True  # pylint: disable=attribute-defined-outside-init
        return self._htmlify(self._get(*args, **kwargs))


class ApiResourceList(ApiResource):
    """
    Base mixin for a generic list of API resources.
    """

    pass


# -------------------------------
# The actual resources in our API
# -------------------------------

class Root(flask_restful.Resource, ApiResource):
    """
    The root resource, with links to other resources in the API.
    """

    URL   = "/"

    def _get(self):
        return {
            "_links" : self.make_links({
                "users"     : UserList.URL,
                "customers" : CustomerList.URL,
            })
        }


class _UserDataEmbedder:
    """
    A mixin that provides a function to embed a user list in a result.
    """

    def embed_user_data_in_result(self, res, user_data):
        for user in user_data:
            res['_embedded']['users'].append(
                {
                    "id"     : user.doc_id,
                    "email"  : user['email'],
                    "_links" : self.make_links({"self" : User.get_self_url(user.doc_id)})
                }
            )


class UserList(flask_restful.Resource, ApiResourceList, _UserDataEmbedder):
    """
    A list of users.
    """

    URL   = "/users"

    def _get(self):
        """
        Return the raw user table data.
        """
        user_data = DB_USER_TABLE.all()

        res = {
            "total_queried" : len(user_data),
            "_embedded"     : {
                "users" : []
            },
            "_links"        : self.make_links({
                                  "self" :         UserList.get_self_url(),
                                  "contained_in" : Root.get_self_url()
                              })
        }

        self.embed_user_data_in_result(res, user_data)
        return res


class User(flask_restful.Resource, ApiResource):
    """
    An individual user.
    """

    URL = "/users/<user_id>"

    def _get(self, user_id):
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
                            "customers" :    UserCustomerList.get_self_url(user.doc_id)
                        })
        return res


class _CustomerDataEmbedder:
    """
    A mixin that provides a function to embed a customer list in a result.
    """

    def embed_customer_data_in_result(self, res, cust_data):
        for cust in cust_data:
            res['_embedded']['customers'].append(
                {
                    "id"     : cust.doc_id,
                    "name"   : cust['name'],
                    "_links" : self.make_links({"self" : Customer.get_self_url(cust.doc_id)})
                }
            )


class UserCustomerList(flask_restful.Resource, ApiResourceList, _CustomerDataEmbedder):
    """
    List of customers for a given user.
    """

    URL = "/users/<user_id>/customers/"

    def _get(self, user_id):
        """
        Return the raw data for a resource, which embeds the user's customers.
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
                "customers" : []
            },
            "_links"        : self.make_links({
                                  "self"         : UserCustomerList.get_self_url(user_id),
                                  "contained_in" : User.get_self_url(user_id)
                              })
        }

        self.embed_customer_data_in_result(res, cust_data)
        return res


class CustomerUserList(flask_restful.Resource, ApiResourceList, _UserDataEmbedder):
    """
    List of customers for a given user.
    """

    URL = "/customers/<customer_id>/users/"

    def _get(self, customer_id):
        """
        Return the raw data for a resource, which embeds the customer's users.
        """
        rels_q    = Query()
        rel_data  = DB_USER_CUSTOMER_RELS_TABLE.search(rels_q.customer_id == int(customer_id))
        user_ids  = [r['user_id'] for r in rel_data]
        # We don't seem to have a way to retrieve a set of objects via a set of ids?
        # Doing it just in a loop for now...
        user_data = [DB_USER_TABLE.get(doc_id=_id) for _id in user_ids]

        res = {
            "total_queried" : len(user_data),
            "_embedded"     : {
                "users" : []
            },
            "_links"        : self.make_links({
                                  "self"         : CustomerUserList.get_self_url(customer_id),
                                  "contained_in" : Customer.get_self_url(customer_id)
                              })
        }

        self.embed_user_data_in_result(res, user_data)
        return res


class CustomerList(UserCustomerList, _CustomerDataEmbedder):
    """
    A list of customers.
    """

    URL = "/customers"

    def _get(self):
        """
        Return the raw user table data.
        """
        cust_data = DB_CUSTOMER_TABLE.all()

        res = {
            "total_queried" : len(cust_data),
            "_embedded"     : {
                "customers" : []
            },
            "_links"        : self.make_links({
                                  "self" :         CustomerList.get_self_url(),
                                  "contained_in" : Root.get_self_url()
                              })
        }

        self.embed_customer_data_in_result(res, cust_data)
        return res



class Customer(flask_restful.Resource, ApiResource):
    """
    An individual customer.
    """

    URL = "/customers/<customer_id>"

    def _get(self, customer_id):
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
            "users"        : CustomerUserList.get_self_url(cust.doc_id)
        }

        # A customer may have a parent customer
        parent_id = cust.get('parent_id')
        if parent_id is not None:
            link_spec['parent'] = Customer.get_self_url(parent_id)

        res['_links'] = self.make_links(link_spec)
        return res


# ----------------------------------------------------
# Registering the resource classes with our Flask app.
# ----------------------------------------------------
for resource_class in [Root,
                       UserList, User, UserCustomerList,
                       Customer, CustomerList, CustomerUserList]:
    API.add_resource(resource_class, resource_class.URL)
