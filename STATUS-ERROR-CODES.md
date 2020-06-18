# Summary of status- and error-codes to be returned by an implementation

The follow HTTP status codes should be used by the ITSM REST implementation.
They are recognized and can be dealt with by our client implementation:

## Success

### 200: Ok

Successful GET or PUT requests.

### 201: Created

Successful POST requests (note that the new resource's URL needs to be
contained in the "Location" header in the response).

## Client errors

Note that any '4**' error code indicates that it's possible for the client
to fix the situation by changing something in their request. Thus, for any
'4**' error, the return body should contain a human readable error message
explaining the problem. The maintainers of the client code can see those
messages and can use it to improve the cient implementation.

In general, any requests that received a '4**' response will NOT be automatically
retried by the client, but may be retried at a later time if and when manual fixes
have been applied to the client code or configuration.

### 400: Bad Request

If there is something wrong with the request body (in case of POST or PUT),
or if the query parameters (for some GET requests) are wrong. This includes
situation where the request is correctly formatted (correct syntax), but
where the request is still wrong in a sematic sense. An example here is the
creation of a user/customer association, where the specified association
exists already.

### 401: Unauthorized

The client could not be authenticated (note that the official name of this
return code is "Unauthorized", but by convention, it is used to indicate
that the authentication failed. This can happen if the client tried to access
a resource that requires authentication, but that no or incorrect credentials
were provided. Note that the 'WWW-Authenticate' header needs to be returned
in that case.

### 403: Forbidden

This should be returned if a client could be authenticated, but this client
does not have the permission to access a given resource.

### 404: Not Found

The requested resource (URL) could not be found or does not exist.

### 405: Method Not Allowed

The method is not allowed on this resource (URL). For example, issuing
a PUT request to a resource that does not allow for updates.

### 406: Not Acceptable

If the 'Accept' header in the client's request demands a content type that
the server is not prepared to deliver.

### 415: Unsupported Media Type

Indicates an unsupported media type: The client sent a request body with
a content type that the server cannot process.

### 4**

Any other '4**' error will be logged.


## Server errors

Note that a '5**' error indicates a problem on the server side, something that
a client cannot fix by changing something in its request.

Since some '5**' errors indicate conditions that may be temporary, some of those
errors may prompt the client to retry the request at a later time, potentially multiple
times. It is important that the server implementation does NOT produce state on its end
(maybe by partially processing a request before failing) that cannot deal with a retry.

The following 500, 502, 503 and 504 errors may result in a retry and thus should be
implemented carefully by the server:

### 500: Internal Server Error

This could mean any kind of error, permanent or temporary. Since the client doesn't
know more, it may as well retry.
    
### 502: Bad Gateway

This often is caused either by configuration issues and may be retried.
      
### 503: Service Unavailable

Typically used to indicate a temporary failure and may be retried.

### 504: Gateway Timeout

Similar to 502, but more often caused by temporary network issues. May be retried.

### Any other '5**' may NOT be retried!

Other '5**' error codes may also be returned (they will be logged on the
client's end), but generally will not result in a retry.
