"""
create_openapi_definition.py.

This script is used to create a full OpenAPI v3 definition file in yaml, which
is then uploaded to Aportio's Swaggerhub profile and can be found at
https://app.swaggerhub.com/apis-docs/aportio/Aportio-ITSM-REST-API-Reference/0.1

This file holds the base definition, where various metadata is pre-filled.
The definitions for the Aportio API's resources can be found in the
openapi_resource_definition folder. That folder has the following sub-folders:

Root                        - The root resource of the API. Essentially, a list
                              of the available top-level resources.

top_level_list_resources    - The top-level resources of the API, such as
                              UserList, TicketList, AttachmentList etc.

individual_resources        - The individual resources, such as getting a
                              specific User by user_id, or a specific Ticket
                              by ticket_id.

second_level_list_resources - Second-level list resources, such as the list of
                              tickets for a given user, or the list of users
                              for a given customer.

Each of these sub-folders has yet more sub-folders for the resource that
belongs in that category. For example, the UserList resource belongs in the
top-level list resources folder, while the single Ticket resource belongs in
the individual resources folder.

Inside each of those resource folders are yaml files, which each contain an
OpenAPI definition that describes how an HTTP method for that resource should
work. These yaml files are named for the HTTP method that they represent for
that API resource, which is any valid HTTP method that we support for that
resource, e.g. "get.yaml", "post.yaml", "put.yaml" etc.

Once finished, the final OpenAPI definition will be written to a file called
Aportio_REST_API_definition_<datetime>, where "datetime" is the date and
time that the script was run.

"""

import datetime
import os

from itsm_api    import views

from ruamel.yaml import YAML


def _replace_angle_brackets(url_string):
    """
    Replace angle brackets with braces in a given url.

    Swaggerhub prefers URLs with variables to have curly braces instead of
    angle brackets, so this replaces all instances of angle brackets with curly
    braces. For example:

    /users/<user_id> -> /users/{user_id}

    """
    return url_string.replace("<", "{").replace(">", "}")


RESOURCE_PATH_LOOKUP = {
    # Root-level resource
    "Root"                        : _replace_angle_brackets(views.Root.URL),

    # Top-level list resources
    "UserList"                    : _replace_angle_brackets(views.UserList.URL),
    "CustomerList"                : _replace_angle_brackets(views.CustomerList.URL),
    "TicketList"                  : _replace_angle_brackets(views.TicketList.URL),
    "CommentList"                 : _replace_angle_brackets(views.CommentList.URL),
    "AttachmentList"              : _replace_angle_brackets(views.AttachmentList.URL),
    "CustomerUserAssociationList" : _replace_angle_brackets(views.CustomerUserAssociationList.URL),

    # Individual resources
    "User"                        : _replace_angle_brackets(views.User.URL),
    "Customer"                    : _replace_angle_brackets(views.Customer.URL),
    "Ticket"                      : _replace_angle_brackets(views.Ticket.URL),
    "Comment"                     : _replace_angle_brackets(views.Comment.URL),
    "Attachment"                  : _replace_angle_brackets(views.Attachment.URL),
    "CustomerUserAssociation"     : _replace_angle_brackets(views.CustomerUserAssociation.URL),

    # Second-level list resources
    "UserCustomerList"            : _replace_angle_brackets(views.UserCustomerList.URL),
    "CustomerUserList"            : _replace_angle_brackets(views.CustomerUserList.URL),
    "CustomerTicketList"          : _replace_angle_brackets(views.CustomerTicketList.URL),
    "UserTicketList"              : _replace_angle_brackets(views.UserTicketList.URL)
}

# Allowed HTTP methods
ALLOWED_HTTP_METHODS = ["get", "post", "put"]

# The base OpenAPI definition, pre-filled with some metadata. Our resource definitions go into
# "paths".
openapi_definition = {
    "openapi": "3.0.1",
    "info": {
        "title": "Aportio ITSM REST API reference",
        "description": "Reference documentation for Aportio's ITSM REST API.",
        "version": "0.1"
    },
    "tags": [
        {
            "name": "Root",
            "description": "The root level of the API"
        },
        {
            "name": "User",
            "description": "Requests against user resources"
        },
        {
            "name": "Ticket",
            "description": "Requests against ticket resources"
        },
        {
            "name": "Customer",
            "description": "Requests against customer resources"
        },
        {
            "name": "Comment",
            "description": "Requests against comment resources"
        },
        {
            "name": "Attachment",
            "description": "Requests against attachment resources"
        },
        {
            "name": "CustomerUserAssociation",
            "description": "Requests against customer-user association resources"
        }
    ],
    # It's nice to have the paths for our definitions in order, starting from Root, since they
    # will show up in that order on Swaggerhub.
    "paths": {path_value: dict() for key, path_value in RESOURCE_PATH_LOOKUP.items()}
}

# Create a YAML object from ruamel.yaml for loading and dumping yaml data.
# Here we're using the ruamel.yaml library because it handles string block scalars better than
# pyyaml.
# A string block scalar in yaml is this:
#
# value: |
#   {
#       "_links": {
#           "self": {
#               "href": "/"
#           },
#           "users": {
#               "href": "/users"
#           },
#           "customers": {
#               "href": "/customers"
#           },
#           "tickets": {
#               "href": "/tickets"
#           },
#           "comments": {
#               "href": "/comments"
#           },
#           "attachments": {
#               "href": "/attachments"
#           },
#           "customer_user_associations": {
#               "href": "/customer_user_associations"
#           }
#       }
#   }
yaml = YAML()

if __name__ == "__main__":
    # Recursively go through the openapi_resource_definitions directory to get each resource's
    # OpenAPI definition, and add it to the base openapi definition object.
    for dirpath, dirnames, files in os.walk("openapi_resource_definitions"):
        # If dirnames is an empty list, it means we are at the end of a branch in the directory
        # tree, which means the yaml files for one of the resources should be in this
        # directory.
        if not dirnames:
            # Get the name of the resource that we're processing.
            # dirpath is a directory path string that looks like this:
            #
            # openapi_resource_definitions/individual_resources/Attachment
            #
            # Where the last part of the string is the name of the directory that contains the
            # definition files we need. In this example, "Attachment" is the name of the
            # resource we need.
            resource_name = os.path.split(dirpath)[-1]
            # Iterate through the list of definition files for each HTTP method inside that
            # resource's folder.
            for def_file in files:
                # Get the path to the definition file.
                path_to_file = os.path.join(dirpath, def_file)
                # Get the type of HTTP method from the file name by removing the ".yaml" file
                # extension from the string.
                http_method = def_file[:-len(".yaml")]
                # File names for our resource definitions should be in the form of:
                # "get.yaml"
                # "post.yaml"
                # or some other RESTful HTTP method that we support in our API. If the current
                # file being processed isn't like that, then we skip over that file since it's
                # not a resource definition.
                if http_method not in ALLOWED_HTTP_METHODS:
                    continue
                # Load the yaml data from the current file being processed
                with open(path_to_file, "r") as yaml_file:
                    definition        = yaml.load(yaml_file)
                    resource_url_path = RESOURCE_PATH_LOOKUP[resource_name]
                    # Set the value of the resource path in the base dictionary to the
                    # definition we loaded from the yaml file. It will look something like this
                    # in the paths dictionary:
                    #
                    # paths:
                    #   /:
                    #     get:
                    #       ...
                    openapi_definition['paths'][resource_url_path][http_method] = definition

    # Get the date and time that the script was run, then generate a name for the definition
    # file.
    # We generate the file name with the date and time so that we can keep different versions
    # of the OpenAPI definition, in case we need to quickly revert back to an older version.
    now      = datetime.datetime.now()
    filename = f"Aportio_REST_API_definition_{now}.yaml"

    # Save the full definition to a file
    with open(filename, "w") as yaml_file:
        yaml.dump(openapi_definition, yaml_file)

    # Output the name of the file that the definition was saved to
    print("*" * 80)
    print(f"Saved definition to file: {filename}")
    print("*" * 80)
