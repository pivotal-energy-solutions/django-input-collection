var DjangoInputCollection = (function(){
    var api = {
        endpointPrefix: '/api',
        endpointPaths: {
            submit: '/input/'
        },
        endpointMethods: {
            submit: 'post'
        },
        payloadGetters: {
            submit: function(instrumentId, data) {
                return {
                    instrument: instrumentId,
                    data: data
                };
            }
        },
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
