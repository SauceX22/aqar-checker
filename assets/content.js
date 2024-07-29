Object.defineProperty(navigator, "languages", {
	get: function () {
		return ["en-US", "en"];
	},
});

Object.defineProperty(navigator, "plugins", {
	get: function () {
		return [1, 2, 3, 4, 5];
	},
});

const getParameter = WebGLRenderingContext.prototype.getParameter;
WebGLRenderingContext.prototype.getParameter = function (parameter) {
	// UNMASKED_VENDOR_WEBGL
	if (parameter === 37445) {
		return "Intel Open Source Technology Center";
	}
	// UNMASKED_RENDERER_WEBGL
	if (parameter === 37446) {
		return "Mesa DRI Intel(R) Ivybridge Mobile ";
	}
	return getParameter(parameter);
};
