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

    with app.test_client() as client:
        with app.app_context():
            init_db()
        yield client

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
            'self': {'href': '/'},
            'users': {'href': '/users'},
            'customers': {'href': '/customers'},
            'tickets': {'href': '/tickets'},
            'comments': {'href': '/comments'},
            'customer_user_associations': {'href': '/customer_user_associations'}
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
    assert msg['location'] == "/users/5"
    assert msg['msg'] == "Ok"

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
        'customers': {'href': '/users/5/customers/'},
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
    assert desc['location'] == "/customer_user_associations/7"
    assert desc['msg'] == "Ok"

    # Get the association and ensure correctness
    rv = client.get(desc['location'], **JSON_HDRS_READ)
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
            'users': {'href': '/customers/1/users/'},
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
            'self': {'href': '/customers/1/users/'},
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
            'self': {'href': '/users/1/customers/'},
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
                         "status" : "OPEN",
                         "classification" : {"l1" : "service-request"}
                     }))
    assert rv.is_json  and  rv.status_code == 201
    msg = rv.get_json()
    assert rv.headers.get('location') == "http://localhost/tickets/5"
    assert msg['location'] == "/tickets/5"
    assert msg['msg'] == "Ok"

    new_ticket_url = msg['location']

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
        "status"         : "CLOSED",
        "classification" : {"l1" : "service-request", "l2" : "foo"}
    }
    rv = client.put(new_ticket_url, **JSON_HDRS_READWRITE,
                    data = json.dumps(new_ticket_def))
    assert rv.is_json  and  rv.status_code == 200

    # Retrieve the ticket data and confirm change
    rv = client.get(new_ticket_url, **JSON_HDRS_READ)
    data = rv.get_json()
    print(data)
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

    # Now let's examine the embeded comments and worknotes
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
        'user_id': 1,
        'ticket_id': 1,
        'text': 'Can I please have an update on this?',
        'type': 'COMMENT'
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
    msg = rv.get_json()
    assert rv.headers.get('location') == "http://localhost/comments/3"
    assert msg['location'] == "/comments/3"
    assert msg['msg'] == "Ok"

    comment = client.get(msg['location'], **JSON_HDRS_READ).get_json()
    assert comment['type'] == "WORKNOTE"
    assert comment['ticket_id'] == 1
    assert comment['text'] == "This is another text"






