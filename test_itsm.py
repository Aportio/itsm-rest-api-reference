import base64
import flask
import json
import os
import pytest
import shutil
import tempfile

from itsm_api       import app
from itsm_api.views import init_db


JSON_HDRS_READ = {
    'headers' : {
        'Accept' : 'application/json'
    }
}
JSON_HDRS_READWRITE = {
    'headers' : {
        'Accept' : 'application/json',
        'Content-Type' : 'application/json'
    }
}


@pytest.fixture
def client():
    """
    Return new test client for each test.

    This establishes a new application context (which a fresh copy of the
    database) in which the test runs.

    """
    # Create a new temporary copy of the DB file at a unique, temporary location.
    # The temporary DB file used for each test is freshly initialized to whatever we have in
    # db.json-example, so each test always has the same starting point.
    db_fname = tempfile.mktemp() + ".json"
    shutil.copy("db.json-example", db_fname)
    app.config['DB_NAME'] = db_fname
    init_db()

    yield app.test_client()

    os.remove(db_fname)  # delete the temporary database file


def _get_root_links(client):
    """
    Return lookup for all root resource collections.

    This is a small helper function, so we can more easily get the root
    collection URLs.

    """
    rv = client.get('/', **JSON_HDRS_READ)
    assert rv.status_code == 200  and  rv.is_json
    return {key:value['href'] for key, value in rv.get_json()['_links'].items()}


# ------------------
# The test functions
# ------------------

def test_root_resource(client):
    """
    Test the root resource, which should contain links to all other collections.
    """
    rv = client.get('/', **JSON_HDRS_READ)
    assert rv.status_code == 200  and  rv.is_json
    assert rv.get_json() == {
        '_links': {
            'self'                       : {'href': '/'},
            'users'                      : {'href': '/users'},
            'customers'                  : {'href': '/customers'},
            'tickets'                    : {'href': '/tickets'},
            'comments'                   : {'href': '/comments'},
            'attachments'                : {'href': '/attachments'},
            'customer_user_associations' : {'href': '/customer_user_associations'}
        }
    }


def test_create_edit_user(client):
    users_url = _get_root_links(client)['users']
    users     = client.get(users_url, **JSON_HDRS_READ).get_json()
    assert users == {
        'total_queried': 4,
        '_embedded': {
            'users': [
                {
                    'id': 1,
                    'email': ['some@user.com'],
                    '_created': '',
                    '_links': {'self': {'href': '/users/1'}}
                },
                {
                    'id': 2,
                    'email': ['another@user.com', 'with-multiple@emails.com'],
                    '_created': '',
                    '_links': {'self': {'href': '/users/2'}}
                },
                {
                    'id': 3,
                    'email': ['foo@foobar.com'],
                    '_created': '',
                    '_links': {'self': {'href': '/users/3'}}
                },
                {
                    'id': 4,
                    'email': ['someone@somewhere.com'],
                    '_created': '',
                    '_links': {'self': {'href': '/users/4'}}
                }
            ]
        },
        '_links': {'self': {'href': '/users'}, 'contained_in': {'href': '/'}}
    }

    # Now POST a new user with some invalid data
    rv = client.post(users_url, **JSON_HDRS_READWRITE,
                     data = json.dumps({"email" : "invalid"}))
    assert rv.is_json  and  rv.status_code == 400
    desc = rv.get_json()['message']
    assert "email needs to be a list" in desc

    # POST a new user with valid data, but where one of the emails is alredy in use
    rv = client.post(users_url, **JSON_HDRS_READWRITE,
                     data = json.dumps({"email" : ["foo@foobar.com", "some@user.com"]}))
    assert rv.is_json  and  rv.status_code == 400
    desc = rv.get_json()['message']
    assert "user with email 'foo@foobar.com' exists already" in desc

    # POST a fully valid new user, which should result in new user being created
    rv = client.post(users_url, **JSON_HDRS_READWRITE,
                     data = json.dumps({"email" : ["xyz@xys.com", "ggg@fff.com"],
                                        "custom_fields" : {"foo" : "bar"}}))
    assert rv.is_json  and  rv.status_code == 201
    msg = rv.get_json()
    assert rv.headers.get('location') == "http://localhost/users/5"
    new_url = rv.headers.get('location')[len("http://localhost"):]
    assert new_url == "/users/5"

    # Load the user list again and confirm the new user is now present
    users_url = _get_root_links(client)['users']
    users     = client.get(users_url, **JSON_HDRS_READ).get_json()
    assert users['total_queried'] == 5
    embedded_new_user = users['_embedded']['users'][-1]
    assert embedded_new_user['id'] == 5
    assert embedded_new_user['email'] == ["xyz@xys.com", "ggg@fff.com"]
    self_url = embedded_new_user["_links"]["self"]["href"]
    assert self_url == "/users/5"

    # Load the full user from the self URL
    rv = client.get(self_url, **JSON_HDRS_READ)
    assert rv.is_json  and  rv.status_code == 200
    user_data = rv.get_json()
    assert user_data['id'] == 5
    assert user_data['email'] == ["xyz@xys.com", "ggg@fff.com"]
    assert user_data['custom_fields'] ==  {"foo" : "bar"}
    assert '_created' in user_data and user_data['_created']
    assert '_updated' in user_data and user_data['_updated'] == user_data['_created']
    assert user_data['_links'] == {
        'self': {'href': '/users/5'},
        'contained_in': {'href': '/users'},
        'customers': {'href': '/users/5/customers'},
        'tickets': {'href': '/users/5/tickets'}
    }

    # Edit the user. Try to give it an email address that's already in use
    rv = client.put(self_url, **JSON_HDRS_READWRITE,
                    data = json.dumps({"email" : ["xyz@xys.com", "foo@foobar.com"]}))
    assert rv.is_json  and  rv.status_code == 400
    desc = rv.get_json()['message']
    assert "user with email 'foo@foobar.com' exists already" in desc

    # Give it an acceptable email. Note that custom_fields are not present, so they should not
    # be in the user anymore after the update.
    rv = client.put(self_url, **JSON_HDRS_READWRITE,
                    data = json.dumps({"email" : ["xyz@xys.com", "foo123@foobar.com"]}))
    assert rv.is_json  and  rv.status_code == 200
    assert rv.get_json() == {"msg" : "Ok"}

    # Load the full user from the self URL and confirm change was made
    rv = client.get(self_url, **JSON_HDRS_READ)
    assert rv.is_json  and  rv.status_code == 200
    user_data = rv.get_json()
    assert user_data['id'] == 5
    assert user_data['email'] == ["xyz@xys.com", "foo123@foobar.com"]
    assert 'custom_fields' not in user_data


def test_customer_user_association(client):
    associations_url = _get_root_links(client)['customer_user_associations']
    associations     = client.get(associations_url, **JSON_HDRS_READ).get_json()

    # Attempt to create association with user that doesn't exist
    rv = client.post(associations_url, **JSON_HDRS_READWRITE,
                     data = json.dumps({"user_id" : 123, "customer_id" : 1}))
    assert rv.is_json  and  rv.status_code == 400
    desc = rv.get_json()['message']
    assert "unknown user '123'" in desc

    # Attempt to create association that exists already
    rv = client.post(associations_url, **JSON_HDRS_READWRITE,
                     data = json.dumps({"user_id" : 1, "customer_id" : 1}))
    assert rv.is_json  and  rv.status_code == 400
    desc = rv.get_json()['message']
    assert "association between customer and user exists already" in desc

    # Attempt to update existing association
    rv = client.put(associations_url + "/1", **JSON_HDRS_READWRITE,
                     data = json.dumps({"user_id" : 1, "customer_id" : 1}))
    assert rv.is_json  and  rv.status_code == 405
    desc = rv.get_json()['message']
    assert "Method not allowed" in desc

    # Create valid new association
    rv = client.post(associations_url, **JSON_HDRS_READWRITE,
                     data = json.dumps({"user_id" : 3, "customer_id" : 2}))
    assert rv.is_json  and  rv.status_code == 201
    desc = rv.get_json()
    assert rv.headers.get('location') == "http://localhost/customer_user_associations/7"
    new_url = rv.headers.get('location')[len("http://localhost"):]
    assert new_url == "/customer_user_associations/7"

    # Get the association and ensure correctness
    rv = client.get(new_url, **JSON_HDRS_READ)
    assert rv.is_json  and  rv.status_code == 200
    desc = rv.get_json()
    assert desc['id'] == 7
    assert desc['user_id'] == 3
    assert desc['customer_id'] == 2
    assert desc['_embedded'] == {
        'user': {
            'id': 3,
            'email': ['foo@foobar.com'],
            '_created': '',
            '_links': {'self': {'href': '/users/3'}}
        },
        'customer': {
            'id': 2,
            'name': 'Bar Company',
            '_created': '',
            '_links': {'self': {'href': '/customers/2'}}
        }
    }


def test_customer_list(client):
    customers_url = _get_root_links(client)['customers']
    customers     = client.get(customers_url, **JSON_HDRS_READ).get_json()
    assert customers == {
        'total_queried': 3,
        '_embedded': {
            'customers': [
                {
                    'id': 1,
                    'name': 'Foo Company',
                    '_created': '',
                    '_links': {'self': {'href': '/customers/1'}}
                },
                {
                    'id': 2,
                    'name': 'Bar Company',
                    '_created': '',
                    '_links': {'self': {'href': '/customers/2'}}
                },
                {
                    'id': 3,
                    'name': 'Foobar Company',
                    '_created': '',
                    '_links': {'self': {'href': '/customers/3'}}
                }
            ]
        },
        '_links': {
            'self': {'href': '/customers'},
            'contained_in': {'href': '/'}
        }
    }


def test_customer_list_search(client):
    # First test an illegal search term
    customers_url = _get_root_links(client)['customers'] + "?foo=bar"
    rv            = client.get(customers_url, **JSON_HDRS_READ)
    assert rv.status_code == 400
    desc = rv.get_json()['message']
    assert "invalid search key: foo" in desc

    # Now a legal search term, but on the wrong resource (a single customer, but searches are
    # only supported by list resources)
    customers_url = _get_root_links(client)['customers'] + "/1?name=Bar%20Company"
    rv            = client.get(customers_url, **JSON_HDRS_READ)
    assert rv.status_code == 400
    desc = rv.get_json()['message']
    assert "this resource does not support queries" in desc

    # Now a valid query
    customers_url = _get_root_links(client)['customers'] + "?name=Bar%20Company"
    customers     = client.get(customers_url, **JSON_HDRS_READ).get_json()
    assert customers == {
        'total_queried': 1,
        '_embedded': {
            'customers': [
                {
                    'id': 2,
                    'name': 'Bar Company',
                    '_created': '',
                    '_links': {'self': {'href': '/customers/2'}}
                }
            ]
        },
        '_links': {
            'self': {'href': '/customers'},
            'contained_in': {'href': '/'}
        }
    }


def test_user_list_search(client):
    users_url = _get_root_links(client)['users'] + \
                                            "?custom_fields.address.city=Littleville"
    users     = client.get(users_url, **JSON_HDRS_READ).get_json()
    assert users == {
        "total_queried": 1,
        "_embedded": {
            "users": [
                {
                    "id": 2,
                    "email": [
                        "another@user.com",
                        "with-multiple@emails.com"
                    ],
                    "_created": "",
                    "_links": {"self": {"href": "/users/2"}}
                }
            ]
        },
        "_links": {
            "self": {"href": "/users"},
            "contained_in": {"href": "/"}
        }
    }

    # Invalid hierarchical field
    users_url = _get_root_links(client)['users'] + "?bar.baz=foo"
    rv        = client.get(users_url, **JSON_HDRS_READ)
    assert rv.status_code == 400
    desc = rv.get_json()['message']
    assert "invalid search key: bar.baz" in desc

    # Query on list resource
    users_url = _get_root_links(client)['users'] + "?email=foo@foobar.com"
    users     = client.get(users_url, **JSON_HDRS_READ).get_json()
    assert users['total_queried'] == 1
    assert users['_embedded']['users'][0]['id'] == 3
    assert users['_embedded']['users'][0]['email'][0] == "foo@foobar.com"


def test_ticket_list_search(client):
    # Query with numeric parameter
    tickets_url = _get_root_links(client)['tickets'] + "?customer_id=2"
    tickets     = client.get(tickets_url, **JSON_HDRS_READ).get_json()
    assert tickets == {
        "total_queried": 1,
        "_embedded": {
            "tickets": [
                {
                    "id": 2,
                    "aportio_id": "2222",
                    "customer_id": 2,
                    "user_id": 2,
                    "short_title": "Need a new license for Office",
                    "_created": "2020-04-12T14:39:+13:00",
                    "status": "CLOSED",
                    "classification": "service-request",
                    "_links": {"self": {"href": "/tickets/2"}},
                    "_updated": "2020-04-12T14:39:+13:00"
                }
            ]
        },
        "_links": {
            "self": {"href": "/tickets"},
            "contained_in": {"href": "/"}
        }
    }


def test_customer_user_list(client):
    customer_url = _get_root_links(client)['customers'] + "/1"
    customer     = client.get(customer_url, **JSON_HDRS_READ).get_json()
    assert customer == {
        'id': 1,
        'name': 'Foo Company',
        'parent_id': 3,
        '_links': {
            'self': {'href': '/customers/1'},
            'contained_in': {'href': '/customers'},
            'users': {'href': '/customers/1/users'},
            'tickets': {'href': '/customers/1/tickets'},
            'parent': {'href': '/customers/3'}
        }
    }

    # Get the user list
    customer_user_list_url = customer['_links']['users']['href']
    customer_user_list     = client.get(customer_user_list_url, **JSON_HDRS_READ).get_json()
    assert customer_user_list == {
        'total_queried': 2,
        '_embedded': {
            'users': [
                {
                    'id': 1,
                    'email': ['some@user.com'],
                    '_created': '',
                    '_links': {'self': {'href': '/users/1'}}
                },
                {
                    'id': 3,
                    'email': ['foo@foobar.com'],
                    '_created': '',
                    '_links': {'self': {'href': '/users/3'}}
                }
            ]
        },
        '_links': {
            'self': {'href': '/customers/1/users'},
            'contained_in': {'href': '/customers/1'}
        }
    }


def test_customer_ticket_list(client):
    customer_url = _get_root_links(client)['customers'] + "/1"
    customer     = client.get(customer_url, **JSON_HDRS_READ).get_json()
    customer_ticket_list_url = customer['_links']['tickets']['href']
    customer_ticket_list     = \
                    client.get(customer_ticket_list_url, **JSON_HDRS_READ).get_json()
    assert customer_ticket_list['total_queried'] == 3
    # Check just the first ticket to confirm general correctness
    ticket = customer_ticket_list['_embedded']['tickets'][0]
    should_ticket = {
        'id': 1,
        'aportio_id': '1111',
        'customer_id': 1,
        'short_title':
        'Broken laptop',
        'status': 'OPEN',
        'classification': 'incident',
    }
    # Only compare the keys we defined in the should image. Don't bother about links and
    # created timestamps
    assert set(should_ticket.items()).issubset(
                    set([(k,v) for k,v in ticket.items() if k in should_ticket]))


def test_user_customer_list(client):
    user_url = _get_root_links(client)['users'] + "/1"
    user     = client.get(user_url, **JSON_HDRS_READ).get_json()
    user_customer_list_url = user['_links']['customers']['href']
    user_customer_list     = \
                    client.get(user_customer_list_url, **JSON_HDRS_READ).get_json()
    assert user_customer_list == {
        'total_queried': 3,
        '_embedded': {
            'customers': [
                {
                    'id': 1,
                    'name': 'Foo Company',
                    '_created': '',
                    '_links': {'self': {'href': '/customers/1'}}
                },
                {
                    'id': 2, 'name':
                    'Bar Company',
                    '_created': '',
                    '_links': {'self': {'href': '/customers/2'}}
                },
                {
                    'id': 3,
                    'name': 'Foobar Company',
                    '_created': '',
                    '_links': {'self': {'href': '/customers/3'}}
                }
            ],
        },
        '_links': {
            'self': {'href': '/users/1/customers'},
            'contained_in': {'href': '/users/1'}
        }
    }


def test_user_ticket_list(client):
    user_url = _get_root_links(client)['users'] + "/1"
    user     = client.get(user_url, **JSON_HDRS_READ).get_json()
    user_ticket_list_url = user['_links']['tickets']['href']
    user_ticket_list     = \
                    client.get(user_ticket_list_url, **JSON_HDRS_READ).get_json()
    assert user_ticket_list['total_queried'] == 1

    # Check just the first ticket to confirm general correctness
    ticket = user_ticket_list['_embedded']['tickets'][0]
    should_ticket = {
        'id': 1,
        'aportio_id': '1111',
        'customer_id': 1,
        'short_title': 'Broken laptop',
        'status': 'OPEN',
        'classification': 'incident',
    }
    # Only compare the keys we defined in the should image. Don't bother about links and
    # created timestamps
    assert set(should_ticket.items()).issubset(
                    set([(k,v) for k,v in ticket.items() if k in should_ticket]))


def test_create_edit_ticket(client):
    tickets_url = _get_root_links(client)['tickets']
    tickets     = client.get(tickets_url, **JSON_HDRS_READ).get_json()
    assert tickets['total_queried'] == 4

    # Attempt to create a new ticket with missing fields
    rv = client.post(tickets_url, **JSON_HDRS_READWRITE,
                     data = json.dumps({"user_id" : 3, "customer_id" : 2}))
    assert rv.is_json  and  rv.status_code == 400
    desc = rv.get_json()['message']
    assert "missing mandatory key(s): aportio_id, short_title, status, classification" in desc

    ticket_def = {
        "user_id"        : 1,
        "customer_id"    : 1,
        "aportio_id"     : "12233",
        "short_title"    : "Laptop is broken",
        "long_text"      : "It doesn't start up anymore.",
        "status"         : "OPEN",
        "classification" : {"l1" : "service-request"}
    }
    for invalid_data, error_msg in [
                    (
                        # Attempt to create ticket with an aportio ID that exists already
                        {"user_id" : 2, "customer_id" : 2, "aportio_id" : "1111"},
                        "a ticket with aportio ID '1111' exists already"
                    ),
                    (
                        # Attempt to create ticket for user that's not associated with
                        # customer
                        {"user_id" : 3, "customer_id" : 2},
                        "user '3' is not associated with customer '2'"
                    ),
                    (
                        # Attempt to create ticket with invalid status
                        {"status" : "FOO"},
                        "invalid ticket status 'FOO'"
                    ),
                    (
                        # Attempt to create ticket with invalid classification
                        {"classification" : {"foo" : "bar"}},
                        "invalid key(s) in classification: foo"
                    )]:
        invalid_ticket_def = dict(ticket_def)
        invalid_ticket_def.update(invalid_data)
        # Attempt to create ticket
        rv = client.post(tickets_url, **JSON_HDRS_READWRITE,
                         data = json.dumps(invalid_ticket_def))
        assert rv.is_json  and  rv.status_code == 400
        desc = rv.get_json()['message']
        assert error_msg in desc

    # Ceate valid ticket
    rv = client.post(tickets_url, **JSON_HDRS_READWRITE,
                     data = json.dumps({
                         "user_id" : 1,
                         "customer_id" : 1,
                         "aportio_id" : "12233",
                         "short_title" : "Laptop is broken",
                         "long_text" : "It doesn't start up anymore.",
                         "status" : "OPEN",
                         "classification" : {"l1" : "service-request"}
                     }))
    assert rv.is_json  and  rv.status_code == 201
    msg = rv.get_json()
    assert rv.headers.get('location') == "http://localhost/tickets/5"
    new_ticket_url = rv.headers.get('location')[len("http://localhost"):]
    assert new_ticket_url == "/tickets/5"

    # Attempt invalid updates
    for invalid_data, error_msg in [
                    (
                        # Attempt to change aportio ID
                        {"aportio_id" : "11112222"},
                        "cannot change aportio ID"
                    ),
                    (
                        # Attempt to change user ID
                        {"user_id" : 3},
                        "cannot change user ID"
                    ),
                    (
                        # Attempt to change customer ID
                        {"customer_id" : 2},
                        "cannot change customer ID"
                    ),
                    (
                        # Attempt to change status to something invalid
                        {"status" : "FOO"},
                        "invalid ticket status 'FOO'"
                    ),
                    (
                        # Attempt to use invalid data type for classification
                        {"classification" : "FOO"},
                        "classification needs to be a dictionary"
                    ),
                    (
                        # Attempt to add invalid classification
                        {"classification" : {"foo" : "bar"}},
                        "invalid key(s) in classification: foo"
                    )]:
        invalid_ticket_def = dict(ticket_def)
        invalid_ticket_def.update(invalid_data)
        rv = client.put(new_ticket_url, **JSON_HDRS_READWRITE,
                        data = json.dumps(invalid_ticket_def))
        assert rv.is_json  and  rv.status_code == 400
        desc = rv.get_json()['message']
        assert error_msg in desc

    # Perform a valid update to the ticket
    new_ticket_def = {
        "user_id"        : 1,
        "customer_id"    : 1,
        "aportio_id"     : "12233",
        "short_title"    : "Laptop is broken",
        "long_text"      : "It doesn't start up anymore.",
        "status"         : "CLOSED",
        "classification" : {"l1" : "service-request", "l2" : "foo"}
    }
    rv = client.put(new_ticket_url, **JSON_HDRS_READWRITE,
                    data = json.dumps(new_ticket_def))
    assert rv.is_json  and  rv.status_code == 200

    # Retrieve the ticket data and confirm change
    rv = client.get(new_ticket_url, **JSON_HDRS_READ)
    data = rv.get_json()
    assert data['status'] == "CLOSED"
    assert data['classification'] == {'l1': 'service-request', 'l2': 'foo'}


def test_embedded_comments(client):
    ticket_url = _get_root_links(client)['tickets'] + "/1"
    ticket     = client.get(ticket_url, **JSON_HDRS_READ).get_json()
    should_ticket = {
        'id': 1,
        'aportio_id': '1111',
        'customer_id': 1,
        'short_title':
        'Broken laptop',
        'status': 'OPEN',
    }
    # Only compare the keys we defined in the should image. Don't bother about links and
    # created timestamps, and even the embedded comments right now.
    assert set(should_ticket.items()).issubset(
                    set([(k,v) for k,v in ticket.items() if k in should_ticket]))
    assert ticket['classification'] == {'l1': 'incident', 'l2': 'hardware'}

    # Now let's examine the embedded comments and worknotes
    comments  = ticket['_embedded']['comments']
    worknotes = ticket['_embedded']['worknotes']
    assert len(comments) == len(worknotes) == 1

    comment  = comments[0]
    worknote = worknotes[0]

    assert comment['user_id'] == 1
    assert comment['text'] == "Can I please have an update on this?"

    assert worknote['user_id'] == 2
    assert worknote['text'] == "Has there been a follow up?"


def test_read_comment(client):
    ticket_url  = _get_root_links(client)['tickets'] + "/1"
    ticket      = client.get(ticket_url, **JSON_HDRS_READ).get_json()
    comment_url = ticket['_embedded']['comments'][0]['_links']['self']['href']

    comment = client.get(comment_url, **JSON_HDRS_READ).get_json()
    should_comment = {
        'user_id'   : 1,
        'ticket_id' : 1,
        'text'      : 'Can I please have an update on this?',
        'type'      : 'COMMENT'
    }
    assert set(should_comment.items()).issubset(
                    set([(k,v) for k,v in comment.items() if k in should_comment]))
    assert comment['_embedded']['ticket']['id'] == 1
    assert comment['_embedded']['user']['id'] == 1
    assert comment['_embedded']['customer']['id'] == 1


def test_update_comment(client):
    ticket_url  = _get_root_links(client)['tickets'] + "/1"
    ticket      = client.get(ticket_url, **JSON_HDRS_READ).get_json()
    comment_url = ticket['_embedded']['comments'][0]['_links']['self']['href']

    comment_def = {
        "user_id"   : 1,
        "ticket_id" : 1,
        "text"      : "This is an updated text",
        "type"      : "WORKNOTE"
    }
    for invalid_data, error_msg in [
                    (
                        {"user_id" : 333},
                        "unknown user '333'"
                    ),
                    (
                        {"ticket_id" : 333},
                        "unknown ticket '333'"
                    ),
                    (
                        {"user_id" : 2},
                        "user '2' is not associated with ticket customer '1'"
                    ),
                    (
                        {"user_id" : 3},
                        "cannot change user ID in comment '2'"
                    ),
                    (
                        {"ticket_id" : 3},
                        "cannot change ticket ID in comment '2'"
                    ),
                    (
                        {"text" : ""},
                        "length should be between 2 and 25000000 characters"
                    ),
                    (
                        {"type" : "foobar"},
                        "unknown comment type 'FOOBAR'"
                    )]:
        invalid_comment_def = dict(comment_def)
        invalid_comment_def.update(invalid_data)
        rv = client.put(comment_url, **JSON_HDRS_READWRITE,
                        data = json.dumps(invalid_comment_def))
        assert rv.is_json  and  rv.status_code == 400
        desc = rv.get_json()['message']
        assert error_msg in desc

    # Performa valid update
    rv = client.put(comment_url, **JSON_HDRS_READWRITE,
                    data = json.dumps(comment_def))
    assert rv.is_json  and  rv.status_code == 200

    comment = client.get(comment_url, **JSON_HDRS_READ).get_json()
    assert comment['type'] == "WORKNOTE"
    assert comment['ticket_id'] == 1
    assert comment['text'] == "This is an updated text"


def test_create_comment(client):
    comments_url  = _get_root_links(client)['comments']

    # Sanity check current comment list
    comments = client.get(comments_url, **JSON_HDRS_READ).get_json()
    assert comments['total_queried'] == 2

    comment_def = {
        "user_id"   : 1,
        "ticket_id" : 1,
        "text"      : "This is another text",
        "type"      : "WORKNOTE"
    }
    for invalid_data, error_msg in [
                    (
                        {"user_id" : 333},
                        "unknown user '333'"
                    ),
                    (
                        {"ticket_id" : 333},
                        "unknown ticket '333'"
                    ),
                    (
                        {"user_id" : 2},
                        "user '2' is not associated with ticket customer '1'"
                    ),
                    (
                        {"type" : "foo"},
                        "unknown comment type 'FOO'"
                    ),
                    (
                        {"user_id" : 2, "ticket_id" : 3},
                        # Ticket 3 belongs to customer 1
                        "user '2' is not associated with ticket customer '1'"
                    )]:
        invalid_comment_def = dict(comment_def)
        invalid_comment_def.update(invalid_data)
        rv = client.post(comments_url, **JSON_HDRS_READWRITE,
                         data = json.dumps(invalid_comment_def))
        assert rv.is_json  and  rv.status_code == 400
        desc = rv.get_json()['message']
        assert error_msg in desc

    # Create a valid comment
    rv = client.post(comments_url, **JSON_HDRS_READWRITE,
                     data = json.dumps(comment_def))
    assert rv.is_json  and  rv.status_code == 201
    assert rv.headers.get('location') == "http://localhost/comments/3"
    # Should receive full representation of new resource as response
    post_response = rv.get_json()
    new_url = rv.headers.get('location')[len("http://localhost"):]

    # Now query it on the new URL
    comment = client.get(new_url, **JSON_HDRS_READ).get_json()
    assert comment['type'] == "WORKNOTE"
    assert comment['ticket_id'] == 1
    assert comment['text'] == "This is another text"

    # Should be the same as what we got in our POST response
    assert post_response == comment


def test_attachments_list(client):
    # Get the url to the attachments list resource, then get the list of attachments that are
    # currently stored in the database.
    attachments_url = _get_root_links(client)['attachments']
    attachments     = client.get(attachments_url, **JSON_HDRS_READ).get_json()

    # Make sure that what we see is exactly what was stored in the database
    assert attachments == {
        "total_queried": 2,
        "attachments": [
            {
                "ticket_id": 1,
                "filename": "test.txt",
                "content_type": "text/plain",
                "_created": "2020-06-12T12:09:25.431621",
                "_updated": "2020-06-12T12:09:25.431621",
                "_links": {
                    "self": {
                        "href": "/attachments/1"
                    }
                }
            },
            {
                "ticket_id": 2,
                "filename": "mt-fuji.jpeg",
                "content_type": "image/jpeg",
                "_created": "2020-06-12T14:09:26.813168",
                "_updated": "2020-06-12T14:09:26.813168",
                "_links": {
                    "self": {
                        "href": "/attachments/2"
                    }
                }
            }
        ],
        "_links": {
            "self": {
                "href": "/attachments"
            },
            "contained_in": {
                "href": "/"
            }
        }
    }


def test_get_attachment(client):
    # First check we get the proper response when trying to get an attachment that doesn't
    # exist
    no_attachment_url = _get_root_links(client)['attachments'] + "/999"
    no_attach_resp    = client.get(no_attachment_url, **JSON_HDRS_READ)
    assert no_attach_resp.is_json and no_attach_resp.status_code == 404

    resp_message = no_attach_resp.get_json()['message']
    assert resp_message == "attachment '999' not found!"

    # Get a ticket that has a attachment
    ticket_url = _get_root_links(client)['tickets'] + "/1"
    ticket     = client.get(ticket_url, **JSON_HDRS_READ).get_json()

    # Get an attachment from that ticket
    attachment_url = ticket['_embedded']['attachments'][0]['_links']['self']['href']
    attachment     = client.get(attachment_url, **JSON_HDRS_READ).get_json()

    # Create a dict that represents what the response for the attachment should look like
    should_attachment = {
        'id'              : 1,
        "ticket_id"       : 1,
        "filename"        : "test.txt",
        "content_type"    : "text/plain",
        "attachment_data" : "VGhpcyBpcyBhIHRlc3QgZmlsZSB0byBja"
                            "GVjayB0aGF0IHRoZSByZXN0IEFQSSB3b3Jrcwo=",
        "_created"        : "2020-06-12T12:09:25.431621",
        "_updated"        : "2020-06-12T12:09:25.431621",
    }

    # Check that the data from the attachment matches the dict with the "should" data
    assert set(should_attachment.items()).issubset(
                set([(k,v) for k,v in attachment.items() if k in should_attachment]))
    assert attachment['_embedded']['ticket']['id'] == 1


def test_embedded_attachments_in_ticket(client):
    # Get a ticket that has a attachment
    ticket_url = _get_root_links(client)['tickets'] + "/1"
    ticket     = client.get(ticket_url, **JSON_HDRS_READ).get_json()

    should_ticket = {
        'id'             : 1,
        'aportio_id'     : '1111',
        'customer_id'    : 1,
        'short_title'    :
        'Broken laptop',
        'status'         : 'OPEN',
    }

    # Only compare the keys we defined in the should image. Don't bother about links and
    # created timestamps, and even the embedded comments right now.
    assert set(should_ticket.items()).issubset(
                    set([(k,v) for k,v in ticket.items() if k in should_ticket]))
    assert ticket['classification'] == {'l1': 'incident', 'l2': 'hardware'}

    # Now examine the embedded attachments
    attachments = ticket['_embedded']['attachments']
    attachment  = attachments[0]

    assert attachment['filename'] == "test.txt"
    assert attachment['content_type'] == "text/plain"
    assert attachment['_created'] == attachment['_updated']


def test_post_attachment(client):
    # Get the url to the attachments list resource
    attachments_url = _get_root_links(client)['attachments']

    # Try to post a new attachment with missing data.
    post_resp = client.post(attachments_url, **JSON_HDRS_READWRITE,
            data = json.dumps({"ticket_id": "1", "filename": "somefile.txt",
                               "content_type": "text/plain"}))

    assert post_resp.is_json and post_resp.status_code == 400
    resp_message = post_resp.get_json()['message']
    assert resp_message == "Bad Request - missing mandatory key(s): attachment_data"

    # Now try with all the mandatory keys, but for an attachment that doesn't exist
    post_resp = client.post(attachments_url, **JSON_HDRS_READWRITE,
            data = json.dumps({"ticket_id"       : "999",
                               "filename"        : "somefile.txt",
                               "content_type"    : "text/plain",
                               "attachment_data" : "Just gibberish"}))

    assert post_resp.is_json and post_resp.status_code == 400
    resp_message = post_resp.get_json()['message']
    assert resp_message == "Bad Request - key 'ticket_id': unknown ticket '999'"

    # Now post an attachment with valid data
    # First, we have to assign a variable with an attachment file that has been base64 encoded
    # (and decoded into a string)
    with open("test_data/text_to_post.txt", "rb") as image_attachment:
        encoded_image_attachment = base64.b64encode(image_attachment.read()).decode()

    # Post the data and check that it was created
    post_resp = client.post(attachments_url, **JSON_HDRS_READWRITE,
            data = json.dumps({"ticket_id": "1",
                               "filename": "text_to_post.txt",
                               "content_type": "text/plain",
                               "attachment_data": encoded_image_attachment}))

    assert post_resp.is_json and post_resp.status_code == 201
    assert post_resp.headers.get('location') == "http://localhost/attachments/3"

    # Load the attachments list to confirm that the attachment was saved
    attachments = client.get(attachments_url, **JSON_HDRS_READ).get_json()
    assert attachments['total_queried'] == 3

    # Get the newest attachment entry and check the fields
    newest_attachment_entry = attachments['attachments'][-1]
    assert newest_attachment_entry['ticket_id'] == 1
    assert newest_attachment_entry['filename'] == "text_to_post.txt"
    assert newest_attachment_entry['content_type'] == "text/plain"
    assert newest_attachment_entry['_created'] == newest_attachment_entry['_updated']
    self_url = newest_attachment_entry['_links']['self']['href']
    assert self_url == "/attachments/3"

    # Get the newest attachment using its URL and check its fields (they should be the same
    # as what we just saw in the attachments list)
    get_resp = client.get(self_url, **JSON_HDRS_READ)
    assert get_resp.is_json and get_resp.status_code == 200

    attachment_data = get_resp.get_json()
    assert attachment_data['ticket_id'] == newest_attachment_entry['ticket_id']
    assert attachment_data['filename'] == newest_attachment_entry['filename']
    assert attachment_data['content_type'] == newest_attachment_entry['content_type']
    assert attachment_data['attachment_data'] == encoded_image_attachment
    assert attachment_data['_created'] == newest_attachment_entry['_created']
    assert attachment_data['_updated'] == newest_attachment_entry['_updated']
    assert attachment_data['_links'] == {
        'self': {'href': '/attachments/3'},
        'contained_in': {'href': '/attachments'}
    }

    # Finally, check that the correct attachment file was saved to the attachments directory
    # under the correct ticket ID with the correct name
    ticket_id     = str(attachment_data['ticket_id'])
    attachment_id = str(attachment_data['id'])
    path_to_attach_file = os.path.join(f"attachment_storage/{ticket_id}/"
                                       f"{attachment_id}__text_to_post.txt")
    assert os.path.isfile(path_to_attach_file)

    # Check that the contents of that file match the contents of the original file
    original_file_path = os.path.join("test_data", "text_to_post.txt")
    with open(original_file_path, "r") as original_file:
        with open(path_to_attach_file, "r") as posted_file:
            assert posted_file.read() == original_file.read()

    # Remove the directory holding the attachment file that was created from this test
    os.remove(path_to_attach_file)
