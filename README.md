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

# WEBSOCKET /
Устанавливает websocket соединение и передает список каналов, на публикацию которых необходимо подписаться

+ Parameters
    + (array[string], required)
