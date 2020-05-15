# Aportio ITSM-backend REST-API reference implementation

This is a simple reference implementation for a RESTful ITSM backend, which implements
the Aportio ITSM REST API. It allows simple operations to read, create or update users,
customers, tickets and comments. Running and exploring the server will provide a good feel and
documentation of what is expected of any server-side implementation of the API.

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

Install the requirements (ideally in a pre-prepared python3 virtual environment):

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

### Main concepts

* All resources are linked, making the API discoverable. You never need to just know a URL,
you can always find what you need by following from the root resource ("`/`"). You can always
find further links by looking for the `_links` element in returned data.
* New resources are always created via a `POST` request to a collection resources. The
available collection resources can be seen when accessing the root ("`/`") resource. There are
no other collections further down in the hierarchy, which support resource creation.
* Updates to existing resources are done via `PUT` request to the resources full URL.
* When creating (`POST`) or updating (`PUT`) a resource, fields starting with "`_`" never need
to be supplied. For example, `_links` or `_embedded`. Likewise, the `id` field should never be
part of request body.

## Current limitations / TODO

* Creation of customer resources is not supported. It is assumed that in a real world
environment, this is done through the ITSM system's own UI or API.
* Creation of users as well as user/customer associations is only supported to demonstrate and
test capabilities. It is very likely that this would also be managed directly through the
ITSM's UI or API.
* The content type for requests and responses is always `application/json`. This will change
in the future, with resource specific content types, even though we may continue to support
`application/json` as a less preferred content type.
* No `DELETE` methods are implemented for any resources. It should be assumed that those will
be implemented for comments and tickets as well as user/customer associations.
* The `PATCH` method is not implemented. This means any update to resources is done via `PUT`.
Consequently, a complete resource definition always needs to be provided.
* Support for attachments to tickets is not yet implemented.
