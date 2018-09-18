var DjangoInputCollection = (function(){

    /* A valid specification is laid out like this:
     *  {
     *      content_type: 'application/json',
     *      endpoints: {
     *          input: {
     *              list: {
     *                  method: 'GET',
     *                  url: '/api/input/'
     *              },
     *              add: {
     *                  method: 'POST',
     *                  url: '/api/input/'
     *              },
     *              get: {
     *                  method: 'GET',
     *                  url: '/api/input/__id__/',
     *              }
     *          },
     *          // ...etc
     *      }
     *  }
     */
    var utils = {
        extractEmptyContext: function(string, tokenPattern) {
            var tokenPattern = tokenPattern || /__(\w+)__/;
            var tokens = {};
            string.replace(tokenPattern, function(match, name){
                tokens[name] = undefined;
            });
            return tokens;
        },
        fillObject: function(object, source) {
            for (name of utils.locals(object)) {
                object[name] = source[name];
            }
        },
        interpolate: function(string, context, tokenPattern) {
            var tokenPattern = tokenPattern || /__(\w+)__/;
            for (var property in context) {
                if (context.hasOwnProperty(property)) {
                    string = string.replace(tokenPattern, context[property]);
                }
            }
            return string;
        },
        locals: function(o) {
            var properties = new Set([]);
            for (var name in o) {
                if (o.hasOwnProperty(name)) {
                    properties.add(name);
                }
            }
            return properties.values();
        }
    };

    var internals = {
        doAction: function(type, operation, context, payload) {
            return api.sendRequest(type, operation, context, payload);
        }
    };

    var api = {
        specification: undefined,
        api: {
            // Exposed one-liners for accomplishing work via requests

            // TODO: Generate these automatically via the spec
            addInput: function(instrumentId, data) {
                var parent = 'instrument';
                var payload = {instrument: instrumentId, data: data};
                var context = {pk: payload[parent]};
                return internals.doAction('input', 'add', context, payload);
            }
        },
        getRequestArgs: function(type, operation, context, payload) {
            var endpointInfo = api.specification.endpoints[type][operation];
            var url = utils.interpolate(endpointInfo.url, context);
            return {
                url: url,
                method: endpointInfo.method.toLowerCase(),
                data: payload
            };
        },
        getRequest: function(type, method, url) {
            var xhr = new XMLHttpRequest();
            xhr.open(method, url);
            return xhr;
        },
        sendRequest: function(type, operation, context, payload) {
            var requestArgs = api.getRequestArgs(type, operation, context, payload);
            var xhr = api.getRequest(type, requestArgs.method, requestArgs.url);
            var postString = undefined;
            if (requestArgs.method == 'post' || requestArgs.method == 'put') {
                xhr.setRequestHeader('Content-Type', api.specification.content_type);
                postString = JSON.stringify(requestArgs.data);
            }
            xhr.send(postString);
            return xhr;
        },
    };

    return (function constructor(collectorSpecification) {
        api.specification = collectorSpecification;  // TODO: deep copy this
        return api;
    })
})();
