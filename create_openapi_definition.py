import datetime
import os

from itsm_api    import views

from ruamel.yaml import YAML


RESOURCE_PATH_LOOKUP = {
    # Root-level resource
    "Root"                        : views.Root.URL,

    # Top-level list resources
    "UserList"                    : views.UserList.URL,
    "CustomerList"                : views.CustomerList.URL,
    "TicketList"                  : views.TicketList.URL,
    "CommentList"                 : views.CommentList.URL,
    "AttachmentList"              : views.AttachmentList.URL,
    "CustomerUserAssociationList" : views.CustomerUserAssociationList.URL,

    # Individual resources
    "User"                        : views.User.URL,
    "Customer"                    : views.Customer.URL,
    "Ticket"                      : views.Ticket.URL,
    "Comment"                     : views.Comment.URL,
    "Attachment"                  : views.Attachment.URL,
    "CustomerUserAssociation"     : views.CustomerUserAssociation.URL,

    # Second-level list resources
    "UserCustomerList"            : views.UserCustomerList.URL,
    "CustomerUserList"            : views.CustomerUserList.URL,
    "CustomerTicketList"          : views.CustomerTicketList.URL,
    "UserTicketList"              : views.UserTicketList.URL
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
            "name": "Users",
            "description": "Requests against user resources"
        },
        {
            "name": "Tickets",
            "description": "Requests against ticket resources"
        },
        {
            "name": "Customers",
            "description": "Requests against customer resources"
        },
        {
            "name": "Comments",
            "description": "Requests against comment resources"
        },
        {
            "name": "Attachments",
            "description": "Requests against attachment resources"
        },
        {
            "name": "CustomerUserAssociations",
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
    # OpenAPI definition.
    for dirpath, dirnames, files in os.walk("openapi_resource_definitions"):
        # If dirnames is an empty list, it means we are at the end of a branch in the directory
        # tree, which means the yaml files for one of the resources should be in this
        # directory.
        if not dirnames:
            # Get the name of the resource that we're processing.
            # dirpath will look something like:
            #
            # openapi_resource_definitions/individual_resources/Attachment
            #
            # So the resource name will be the last item of dirpath.
            resource_name = os.path.split(dirpath)[-1]
            # Iterate through the list of definition files for each HTTP method inside that
            # resource's folder.
            for def_file in files:
                # Get the path to the definition file.
                path_to_file = os.path.join(dirpath, def_file)
                # Get the type of HTTP method from the file name by removing the ".yaml" file
                # extension from the string.
                http_method = def_file[:-5]
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
                    # definition
                    # we loaded from the yaml file. It will look something like this in the
                    # paths dictionary:
                    #
                    # paths:
                    #   /:
                    #     get:
                    #       ...
                    openapi_definition['paths'][resource_url_path][http_method] = definition

    # Get the date and time for right now, then generate a name for the definition file
    now      = datetime.datetime.now()
    filename = f"Aportio_REST_API_definition_{now}.yaml"

    # save the full definition to a file
    with open(filename, "w") as yaml_file:
        yaml.dump(openapi_definition, yaml_file)

    # Output the name of the file that the definition was saved to
    print("*" * 80)
    print(f"Saved definition to file: {filename}")
    print("*" * 80)
