# Aportio ITSM-backend REST-API reference implementation

This is a simple reference implementation for a RESTful ITSM backend, which implements
the Aportio ITSM REST API. By providing a proxy to map from these APIs to the APIs of
their ITSM system, developers can incorporate InboxAgent's AI-powered, advanced email
parsing and classification features into their own applications and deliver more value
to their customers.

This reference implementation provides simple operations to read, create or update users,
customers, tickets and comments. Running and exploring the server will offer a good feel
as well as live documentation of what is expected of any server-side implementation of
the API.

Refer to our OpenAPI documentation on
[Swaggerhub](https://app.swaggerhub.com/apis-docs/aportio/Aportio-ITSM-REST-API-Reference/0.1)
to get an idea of how requests and responses should be implemented.

## The basic concept

[Aportio](http://aportio.com) provides a hosted service to automatically ingest, parse,
clean, de-clutter and classify incoming emails and recognize ongoing email conversations.
It then creates or updates tickets in our customers' ITSM systems. It directly integrates
with some common ITSM systems in the market. In addition to those ITSM-specific APIs,
Aportio supports a powerful generic RESTful API, which we have defined.

If you are currently using an ITSM system which Aportio does not yet support directly,
or if you have a custom ITSM system, then an adaptor or proxy needs to be provided
between Aportio and the ITSM system. The proxy needs to implement this server-side
RESTful API to allow Aportio to interact with it.

The following diagram illustrates the architecture:

![Aportio-ITSM-proxy-architecture](/media/architecture.png?raw=true "Architecture")

The proxy can be hosted on premises, or in the cloud, as long as cloud-hosted Aportio can
access the RESTful API implemented by the proxy.

## Implementation choices

For the reference implementation in this repository certain implementation choices were made
that are of no consequence to anyone attempting a real-world implementation. Such an
implementor is encouraged to look at the functionality of the API, not how it is implemented
here. Specifically, the choice of database backend, support for a human browseable API, etc.,
can all be ignored.

## Starting the server

You can run the server either via a docker image, or you can locally run the Python sources.
Docker is best suited if you just want to run the server, without having to deal with setting
up a Python environment.

### Running the server in docker (quickest way to see the server in action)

Build the docker image:

    $ docker build . -t aportio_rest_itsm_reference

Run the container, exposing the port:

    $ docker run -p 5000:5000 aportio_rest_itsm_reference

You can visit the running server in your browser on http://localhost:5000.

### Running the server locally (best for local development and examining the code)

System requirements:

* Python 3.6 or higher.
* Reasonably modern Linux (tested with Ubuntu 18.04).
* Ideally, configure a virtual environment for the project.

Install the required packages:

    $ pip install -r requirements/deploy.txt

If you wish to work on the code, please also run:

    $ pip install -r requirements/develop.txt

Copy the example database file to the correct location:

    $ cp db.json-example db.json

Run the server:

    $ python run.py

The server now listens on http://localhost:5000.

When developing code, please use these two test scripts:

    $ ./style_tests.sh    # enforce certain coding style standards, perform static code checks
    $ ./run_tests.sh      # run all unit tests

Unit tests also produce code coverage reports in HTML. Their URL is printed at the end of the
unit test run.


## Exploring the server's RESTful API

The API is RESTful and utilizes JSON for request bodies and responses. For your convenience,
it recognizes when it is accessed via a web browser and displays the data nicely formatted on
a web page, makes links clickable and also displays useful documentation about each resource.

This browser-based exploration of the API is useful, but it is only limited to GET requests.
Any POST requests (to create resources) or PUT requests (to update resources) need to be
performed with utilities such as `curl` or `wget` or via a client application.

### Main resources

* Users: People, identified by their email addresses.
* Customers: Companies or organizations, which are customers of the MSP.
* User/Customer associations: Manages which users are associated with which customer. Note
that a user may be associated with multiple customers.
* Tickets: Tickets that are created by users, which are associated with customers.
* Comments: These are either external or internal notes (often called "comments" or
"worknotes"), which are attached to a ticket.

### Search queries

***(please review the notes at the end of this chapter for real-world implementation considerations)***

A number of collection resources support queries via search parameters in the URL. Various
fields of the resource can be specified in the URL, for example:

    /users?email=john@test.com&email=bar@baz.com

This returns all users which have either the email address 'john@test.com' or 'bar@baz.com'.

Queries can be made for hierarchical parameters as well:

    /customers?custom_fields.address.city=Sample%20Town

This returns a list of all customers in the city 'Sample Town'. Note the URL encoding of the
whitespace. Also note that this of course relies on the presence of a properly structured
'address' custom field.

Note that specifying the same key multiple times ('email' in the example above) is the same as
specifying an OR query: Email should be either one or the other. If you add other parameters
to the query string then this has the effect of an AND. As an example of combining AND and OR
queries, consider the following:

    /users?email=john@test.com&email=bar@baz.com&custom_fields.address.city=Smallville

This returns all users in Smallville, which have either one of the two email addresses.

Search queries are supported on the following resources:

* Users
* Customers
* Tickets
* Customer-User lists (the users associated with a customer)
* User-Customer lists (the customers that a user is associated with)
* Customer-Ticket lists (the tickets belonging to a customer)
* User-Ticket lists (the tickets created by a user)

***Implementation of search/query features for a real-world ITSM system***

The query API mimics a database query. However, it is understood that many ITSMs do not
provide a comparable functionality. The ability to search for different entities may not be
unified, different API calls may be needed, query terms may not be combinable, etc.

Therefore, in a real-world implementation task the system should look for specific
queries and translate them into whichever API calls are necessary. A full implementation of
the capabilities described above (AND/OR across multiple fields) is not necessary.

However, please note that the following queries need to be recognized and supported by a
real-world implementation, by whichever means necessary:

    /customers/<customer-id>/users?email=<user-email>
    /customers/<customer-id>/tickets?user_id=<user-id>
    /customers/<customer-id>/tickets?user_id=<user-id>&status=<status>

### Main concepts

* All resources are linked, making the API discoverable. You never need to just know a URL,
you can always find what you need by following from the root resource ("`/`"). You can always
find further links by looking for the `_links` element in returned data.
* New resources are always created via a `POST` request to a collection resources. The
available collection resources can be seen when accessing the root ("`/`") resource. There are
no other collections further down in the hierarchy, which support resource creation.
* Updates to existing resources are done via `PUT` request to the resources full URL.
* You cannot issue a `PUT` request to a collection resource, or to a URL for a non-existing
resource, since the resource ID is part of its URL, and all IDs are created on the server side
when the resource is created via `POST`.
* When creating (`POST`) or updating (`PUT`) a resource, fields starting with "`_`" never need
to be supplied. For example, `_links` or `_embedded`. Likewise, the `id` field should never be
part of request body.
* A successful `POST` request returns `201 Created` with the location/URL of the new resource
in the `Location:` HTTP header of the response. For the caller's convenience a full
representation of the new resource may (!) be returned in the response body. The caller should
not rely on that, though: The server may decide not to send the full resource, or may only
send a summarized version, for example in case the response is too big. In general it is up to
the server whether to include a resource representation and in what form.
* A successful `PUT` request returns `200 Ok`.
* When creating a new ticket, the `aportio_id` is stored. This is a unique ID created by
Aportio, before attempting to create the ticket via the API. In a real-world implementation,
it is recommended that this is stored in a custom field in the ITSM ticket.
* Many resources contain an `_embedded` section. This section may contain brief summaries for
the various referenced resources. This often provides sufficient information for the most
important attributes of the referenced resource, without requiring extra `GET` requests to get
the entire representation of the referenced resource. However, each embedded resource always
has a `_links` section, with a link to itself (look for `self`). This gives the URL of the
full resource, which can be accessed in case the summary did not contain all the necessary
information.
* Users and customers are associated with each other in a separate record. This means that a
single user may be associated with multiple customers.
* The resource representation generally only contain a small number of top-level attributes.
For example, a Customer resource only consists of a `name` and a `parent_id` (to model
hierarchical relationships between customers). Likewise, the only fixed attribute of a User
resource is the `email` list of addresses. Any other attribute that might be useful needs to
be mapped into the optional `custom_fields` dictionary that can be part of those resources.


## Authentication

The API specification doesn't mandate a particular kind of authentication. Aportio's client for
this API is designed to be flexible and over time support different authentication mechanisms,
as required by customers or 3rd parties who implement the generic API backend.

Currently, Aportio's API client supports two authentication methods:

* `None`: No keys or passwords of any kind are passed through. Obviously, this should not be
  used in production, but may be useful during development.
* `API-key`: A key/value pair is sent in an HTTP header as part of each REST request. The name
  of the key (header) as well as the value is configurable.

When a customer or 3rd party has implemented the generic API backend, they should let Aportio
staff know the authentication type and any additional parameters, so that it can be configured
by Aportio on its production system.

For example, let's say the implementor of the backend API chooses `API-key` as the
authentication method and requires a header named `x-my-auth-key` with a value of
`abc123-some-secret-xyz`. After communicating those values to Aportio, the client will
be configured to send this information with each request. It would appear similar to this:

    GET /<some-url>
    Accept: 'application/json'
    Content-type: application/json
    x-my-auth-key: abc123-some-secret-xyz

    ...

The backend implementation can then use this header to authenticate requests from the Aportio
production site to the backend.

Note that the reference implementation of the API backend in this repository here does not
support or expect ANY authentication.


## Current limitations / TODO

* Creation of customer resources is not supported. It is assumed that in a real world
environment, this is done through the ITSM system's own UI or API.
* Creation of users as well as creation of user/customer associations is only supported to
demonstrate and test capabilities. It is very likely that this would also be managed directly
through the ITSM's UI or API. Therefore, it is fine for a real-world implementation to return
a `405 Method not allowed` error for any `PUT` or `POST` access to those resources. Note,
however, that the `users` and `customer_user_associations` resources need to be made available
at least for `GET` access.
* The content type for requests and responses is always `application/json`. This will change
in the future, with resource specific content types, even though we may continue to support
`application/json` as a less preferred content type.
* No `DELETE` methods are implemented for any resources. It should be assumed that those will
be implemented for comments and tickets as well as user/customer associations.
* The `PATCH` method is not implemented. This means any update to resources is done via `PUT`.
Consequently, a complete resource definition always needs to be provided.
* Support for attachments to tickets is not yet implemented.

## Examples for creating and updating resources

### Create a new ticket

Request:

    POST /tickets
    Accept: 'application/json'
    Content-type: application/json

    {
        "user_id"        : 1,
        "customer_id"    : 1,
        "aportio_id"     : "12233",
        "short_title"    : "Laptop is broken",
        "status"         : "OPEN",
        "classification" : {"l1" : "service-request"},
        "custom_fields"  : {
            "foo"            : "bar",
            "something_else" : [1, 2 "xyz"]
        }
    }

Response:

    201 Created

    Content-type: application/json
    Location: http://localhost/tickets/123

    {
        "id": 123,
        "aportio_id": "12233
        "customer_id": 1,
        "short_title": "Laptop is broken",
        "user_id": 1,
        "_created": "2020-04-12T14:39:+13:00",
        "status": "OPEN",
        "classification": {
            "l1": "service-request",
            ...
        },
        ....

        (full representation of the new resource is returned)
    }

Comments:

* The `aportio_id` is a mandatory field and is unique. It should be stored in the ITSM
backend, possibly in a custom field.
* While `classification` is mandatory, it may be supplied as `{}` in case the classification
itself is provided later.
* The `custom_fields` attribute is optional. It can contain any JSON serializable values. The
assumption is that normally, this will be used to set other fields in the ITSM (customer
defined ones or other standard fields).
* The specified user has to be associated with the customer.

### Edit a ticket

For example to change the ticket status and to provide additional classification.

Request:
    
    PUT /tickets/123
    Accept: 'application/json'
    Content-type: application/json

    {
        "user_id"        : 1,
        "customer_id"    : 1,
        "aportio_id"     : "12233",
        "short_title"    : "Laptop is broken",
        "status"         : "CLOSED",
        "classification" : {"l1" : "service-request", "l2" : "hardware"}
    }

Response:

    200 Ok

    Content-type: application/json

    {
       "msg" : "Ok"
    }

Comments:

* In `classification` the only permissible dictionary keys are `l1`, `l2` and `l3`. However,
the values stored for those keys are completely free-form and will have to be agreed on
beforehand between Aportio and its customer. 

### Post a comment on a ticket

Request:

    POST /comments
    Accept: 'application/json'
    Content-type: application/json

    {
        "user_id"   : 1,
        "ticket_id" : 123,
        "text"      : "This is another comment",
        "type"      : "WORKNOTE"
    }

Response:

    201 Created

    Content-type: application/json
    Location: http://localhost/comments/4567

    {
        "user_id": 1,
        "ticket_id": 123,
        "text": "This is another comment",
        "type": "WORKNOTE",
        "_created": "2020-05-14T14:09:25.431621",
        "_updated": "2020-05-14T14:09:25.431621",
        "id": 1,
        "_embedded": {
            "ticket": {
                "id": 123,
                ...

            }
        },

        ...
        (full representation of the new resource is returned)
    }

Comments:

* Comments can either be of type `COMMENT` or `WORKNOTE`. By convention, a `COMMENT` is usually
what is provided by an end-user, while a `WORKNOTE` is provided by service desk staff.

### Update a comment

    PUT /comments/4567
    Accept: 'application/json'
    Content-type: application/json

    {
        "user_id"   : 1,
        "ticket_id" : 123,
        "text"      : "An updated text",
        "type"      : "COMMENT"
    }

Respone:

    200 Ok

    Content-type: application/json

    {
       "msg" : "Ok"
    }

Comments:

* While a `PUT` request has to contain all the fields in a resource, it is not allowed to
change the `user_id`, or `ticket_id` in an existing comment. Attempting to do so will result
in a `400 Bad request` response.
* It is possible to change the type of comment in an update (for example, from `COMMENT` to
`WORKNOTE`). A real-world ITSM system may not allow this operation. In that case, such an
attempt should return a `400 Bad request` response.
