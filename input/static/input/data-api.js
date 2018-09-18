var DjangoInputCollection = (function(){

    var internals = {
        interpolate: function(string, context, tokenPattern) {
            var tokenPattern = tokenPattern || /__(\w+)__/;
            for (var property in context) {
                if (context.hasOwnProperty(property)) {
                    string = string.replace(tokenPattern, context[property]);
                }
            }
            return string;
        },
        doAction: function(type, operation, context, payload) {
            return api.sendRequest(type, operation, context, payload);
        }
    };

    var api = {
        specification: undefined,
        api: {
            // One-liners for sending archetypical requests
            submit: function(instrumentId, data) {
                return api.sendRequest('submit', instrumentId, data);
            }
        },

        getRequestArgs: function(type, data) {
            return {
                url: api.endpointPrefix + api.endpointPaths[type],
                method: api.endpointMethods[type],
                data: data
            };
        },
        getRequest: function(type, method, url) {
            var xhr = new XMLHttpRequest();
            xhr.open(method, url);
            return xhr;
        },
        sendRequest: function(type, ...dataArgs) {
            var data = api.payloadGetters[type](...dataArgs);
            var requestArgs = api.getRequestArgs(type, data);
            var xhr = api.getRequest(type, requestArgs.method, requestArgs.url);
            var postString = undefined;
            if (requestArgs.method == 'post' || requestArgs.method == 'put') {
                xhr.setRequestHeader('Content-Type', 'application/json');
                postString = JSON.stringify(data);
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
