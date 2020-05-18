# Aportio ITSM-backend REST-API reference implementation

This is a simple reference implementation for a RESTful ITSM backend, which implements
the Aportio ITSM REST API. It allows simple operations to read, create or update users,
customers, tickets and comments. Running and exploring the server will provide a good feel and
documentation of what is expected of any server-side implementation of the API.

Certain implementation choices made in this reference implementation are of no consequence to
anyone attempting a real-world implementation in order to front-end an ITSM backend API. Such
an implementor is encouraged to look at the functionality of the API, not how it is
implemented here. Specifically, the choice of database backend, support for a human browseable
API, etc., can all be ignored.

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

    $ pip install requirements/deploy.txt

If you wish to work on the code, please also run:

    $ pip install requirements/develop.txt

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
it recognizes when it is access via a web browser and displays the data nicely formatted on a
web page, makes links clickable and also displays useful documentation about each resource.

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
* User-Ticket lists (the tickets creatd by a user)


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


## Current limitations / TODO

* Authentication of any kind is not yet implemented.
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
