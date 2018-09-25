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
        tokenPattern: /__(\w+)__/g,
        extractEmptyContext: function(string, tokenPattern) {
            var tokenPattern = tokenPattern || utils.tokenPattern;
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
            var tokenPattern = tokenPattern || utils.tokenPattern;
            for (var property of utils.locals(context)) {
                var value = context[property];
                if (value !== undefined && value !== null) {
                    string = string.replace(tokenPattern, value);
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
        generateApi: function(specification){
            // Expose one-liners for accomplishing work via requests

            var api = {};

            for (var type of utils.locals(specification.endpoints)) {
                for (var operation of utils.locals(specification.endpoints[type])) {
                    var endpointInfo = specification.endpoints[type][operation];
                    var emptyContext = utils.extractEmptyContext(endpointInfo.url);
                    var name = operation + type.charAt(0).toUpperCase() + type.substr(1);

                    api[name] = internals.buildAction(type, operation, emptyContext);
                }
            }

            return api;
        },
        buildAction: function(type, operation, emptyContext) {
            return function(payload, extraContext, csrfToken) {
                var context = Object.assign({}, emptyContext);
                utils.fillObject(context, extraContext);
                if (payload !== undefined) {
                    utils.fillObject(context, payload);
                }
                internals.doAction(type, operation, context, payload, csrfToken);
            };
        },
        doAction: function(type, operation, context, payload, csrfToken) {
            return api.sendRequest(type, operation, context, payload, csrfToken);
        }
    };

    var api = {
        specification: undefined,
        api: undefined,
        getRequestArgs: function(type, operation, context, payload) {
            var endpointInfo = api.specification.endpoints[type][operation];
            var url = utils.interpolate(endpointInfo.url, context);
            if (payload !== undefined) {
                payload.collector = api.specification.collector;
            }
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
        sendRequest: function(type, operation, context, payload, csrfToken) {
            var requestArgs = api.getRequestArgs(type, operation, context, payload);
            var xhr = api.getRequest(type, requestArgs.method, requestArgs.url);
            var postString = undefined;
            if (requestArgs.method == 'post' || requestArgs.method == 'put') {
                xhr.setRequestHeader('Content-Type', api.specification.content_type);
                xhr.setRequestHeader('X-CSRFToken', csrfToken);
                postString = JSON.stringify(requestArgs.data);
            }
            xhr.send(postString);
            return xhr;
        },
    };

    return (function constructor(collectorSpecification) {
        api.specification = collectorSpecification;  // TODO: deep copy this
        api.api = internals.generateApi(api.specification);
        return api;
    })
})();
