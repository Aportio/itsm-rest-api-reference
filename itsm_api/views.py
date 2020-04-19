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
                more_lines.append(line or " ")  # Empty lines become line break
        return ((title or "A resource"), "<br>".join(more_lines))

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

    def _get(self, *args, **kwargs):
        """
        Return the raw data for the resource.
        """
        raise NotImplementedError(f"The _get() function needs to be implemented by "
                                  f"child class '{self.__class__.__name__}'!")

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

    In any resource, look for a `_links` element. It contains references to
    additional or related resources. It also always contains a link to `self`,
    so that it is always clear how we found this resource. For some resources
    there also is a `contained_in` link, which refers to the collection or
    other parent of the current resource.

    """

    URL   = "/"

    def _get(self):
        return {
            "_links" : self.make_links({
                "self"      : Root.get_self_url(),
                "users"     : UserList.get_self_url(),
                "customers" : CustomerList.get_self_url(),
                "tickets"   : TicketList.get_self_url(),
            })
        }


class _UserDataEmbedder:
    """
    A mixin that provides a function to embed a user list in a result.
    """

    def embed_user_data_in_result(self, user_data):
        res = []
        for user in user_data:
            res.append(
                {
                    "id"     : user.doc_id,
                    "email"  : user['email'],
                    "_links" : self.make_links({"self" : User.get_self_url(user.doc_id)})
                }
            )
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
        Return the raw user table data.
        """
        user_data = DB_USER_TABLE.all()

        res = {
            "total_queried" : len(user_data),
            "_embedded"     : {
                "users" : self.embed_user_data_in_result(user_data)
            },
            "_links"        : self.make_links({
                                  "self" :         UserList.get_self_url(),
                                  "contained_in" : Root.get_self_url()
                              })
        }
        return res


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
                            "customers" :    UserCustomerList.get_self_url(user.doc_id),
                            "tickets" :      UserTicketList.get_self_url(user.doc_id)
                        })
        return res


class _CustomerDataEmbedder:
    """
    A mixin that provides a function to embed a customer list in a result.
    """

    def embed_customer_data_in_result(self, cust_data):
        res = []
        for cust in cust_data:
            res.append(
                {
                    "id"     : cust.doc_id,
                    "name"   : cust['name'],
                    "_links" : self.make_links({"self" : Customer.get_self_url(cust.doc_id)})
                }
            )
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
                "customers" : self.embed_customer_data_in_result(cust_data)
            },
            "_links"        : self.make_links({
                                  "self"         : UserCustomerList.get_self_url(user_id),
                                  "contained_in" : User.get_self_url(user_id)
                              })
        }
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
                "users" : self.embed_user_data_in_result(user_data)
            },
            "_links"        : self.make_links({
                                  "self"         : CustomerUserList.get_self_url(customer_id),
                                  "contained_in" : Customer.get_self_url(customer_id)
                              })
        }
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
        Return the raw user table data.
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

    URL = "/customers/<customer_id>"

    def _get(self, customer_id):
        """
        Return the raw data of a customer.
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


class _TicketDataEmbedder:
    """
    A mixin that provides a function to embed a ticket list in a result.
    """

    def embed_ticket_data_in_result(self, ticket_data):
        res = []
        for ticket in ticket_data:
            res.append(
                {
                    "id"             : ticket.doc_id,
                    "aportio_id"     : ticket['aportio_id'],
                    "customer_id"    : ticket['customer_id'],
                    "short_title"    : ticket['short_title'],
                    "created"        : ticket['created'],
                    "status"         : ticket['status'],
                    "classification" : ticket['classification'].get("l1", "(none)"),
                    "_links"         : self.make_links({
                                           "self" : Ticket.get_self_url(ticket.doc_id)
                                       })
                }
            )
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
        Return the raw ticket list data of a customer.
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
        Return the raw ticket list data of a user.
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
        Return the raw ticket table data.
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


class Ticket(flask_restful.Resource, ApiResource):
    """
    An individual service desk ticket.

    A "ticket" represents a service desk ticket that has been created within
    the ITSM backend.

    """

    URL = "/ticket/<ticket_id>"

    def _get(self, ticket_id):
        ticket = DB_TICKET_TABLE.get(doc_id=int(ticket_id))
        if not ticket:
            flask_restful.abort(404, message=f"Ticket '{ticket_id}' not found!")
        res = {
            "id" : ticket.doc_id
        }
        res.update(ticket)
        res['_links'] = self.make_links({
                            "self" :         Ticket.get_self_url(ticket.doc_id),
                            "contained_in" : TicketList.get_self_url(),
                            "customer" :     Customer.get_self_url(res['customer_id']),
                            "user" :         User.get_self_url(res['user_id'])
                        })
        return res


# ----------------------------------------------------
# Registering the resource classes with our Flask app.
# ----------------------------------------------------
for resource_class in [Root,
                       UserList, User, UserCustomerList, UserTicketList,
                       Customer, CustomerList, CustomerUserList, CustomerTicketList,
                       Ticket, TicketList]:
    API.add_resource(resource_class, resource_class.URL)
