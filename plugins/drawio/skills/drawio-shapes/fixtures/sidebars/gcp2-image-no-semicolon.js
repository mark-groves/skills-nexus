Sidebar.prototype.addGCP2Palette = function() {
	this.addGCP2IconsAIAndMachineLearningPalette();
};

Sidebar.prototype.addGCP2IconsAIAndMachineLearningPalette = function() {
	var s = 1;
	var n = 'editableCssRules=.*;html=1;shape=image;aspect=fixed;';
	this.createVertexTemplateEntry(n + 'image=data:image/svg+xml,PHN2ZyB4bWxucz0iaHR0cDovL3d3dy53My5vcmcvMjAwMC9zdmciPjwvc3ZnPg==;',
		s * 34, s * 42, 'Document AI', null, null, null, '');
	this.createVertexTemplateEntry(n + 'image=data:image/svg+xml,PHN2ZyB4bWxucz0iaHR0cDovL3d3dy53My5vcmcvMjAwMC9zdmciLz4=',
		s * 34, s * 42, 'Healthcare API', null, null, null, '');
};
