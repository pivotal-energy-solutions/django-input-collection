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
                    var name = type + operation.charAt(0).toUpperCase() + operation.substr(1);

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
        getRequestInfo: function(type, operation, context, payload, csrfToken) {
            var endpointInfo = api.specification.endpoints[type][operation];
            var method = endpointInfo.method.toLowerCase();
            var headers = headers || {};
            var url = utils.interpolate(endpointInfo.url, context);

            if (method == 'get' || payload !== undefined) {
                payload.collector = api.specification.collector;
            }

            // Append query string suffix if required.  This consumes the 'payload'.
            if (method == 'get') {
                var params = [];
                for (var k in payload) {
                    if (payload.hasOwnProperty(k)) {
                        var key = encodeURIComponent(k);
                        var value = encodeURIComponent(payload[k]);
                        params.push(key + '=' + value);
                    }
                }
                url += '?' + params.join('&');
                payload = undefined;  // So it doesn't do anything during xhr.send(payload);
            }

            headers['Content-Type'] = api.specification.content_type;
            if (csrfToken !== undefined) {
                headers['X-CSRFToken'] = csrfToken;
            }

            return {
                url: url,
                method: method,
                data: payload,
                headers: headers
            };
        },
        prepareRequest: function(args) {
            var xhr = new XMLHttpRequest();
        sendRequest: function(type, operation, context, payload, csrfToken) {
            var requestArgs = api.getRequestArgs(type, operation, context, payload);
            var xhr = api.getRequest(type, requestArgs.method, requestArgs.url);
            xhr.open(args.method, args.url);

            // Finalize headers
            for (var k in args.headers) {
                if (payload.hasOwnProperty(k)) {
                    xhr.setRequestHeader(k, args.headers[k]);
                }
            }

            // Finalize POST payload
            var postString = undefined;
            if (args.method != 'get' && payload !== undefined) {
                postString = JSON.stringify(args.data);
            }

            // Return promise-compatible trigger function
            return (function doRequest(resolve, reject) {
                return xhr.send(postString);
            });
        },
        },
    };

    return (function constructor(collectorSpecification) {
        api.specification = collectorSpecification;  // TODO: deep copy this
        api.api = internals.generateApi(api.specification);
        return api;
    })
})();
