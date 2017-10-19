FORMAT: 1A

# POST /publish
+ Request (application/json)
    + Attributes (object)
        + channel (string, required)
        + data (object, required)
    + Body

            {"channel": "anYkadl3"
             "data": {"field": "value"}
             }
+ Response 200 (application/json)
    + Attributes (object)
        + success (boolean, required)
    + Body

            {"success" : true}

# POST /order (DEPRECATED)
+ Request (application/json)
    + Attributes (object)
        + order_id (string, required)
        + state (enum[string], required)
            + Members
                + `done`
                + `reload`
    + Body

            {"order_id": "anYkid"
             "state": "reload"}
+ Response 200 (application/json)
    + Attributes (object)
        + success (boolean, required)
    + Body

            {"success" : true}
