def is_css(self) -> bool:
    """Return True if file is a CSS file."""
    return self.src_uri.endswith('.css')

----------

def test_md_readme_index_file_use_directory_urls(self):
    f = File('README.md', '/path/to/docs', '/path/to/site', use_directory_urls=True)
    self.assertEqual(f.src_uri, 'README.md')
    self.assertPathsEqual(f.abs_src_path, '/path/to/docs/README.md')
    self.assertEqual(f.dest_uri, 'index.html')
    self.assertPathsEqual(f.abs_dest_path, '/path/to/site/index.html')
    self.assertEqual(f.url, './')
    self.assertEqual(f.name, 'index')
    self.assertTrue(f.is_documentation_page())
    self.assertFalse(f.is_static_page())
    self.assertFalse(f.is_media_file())
    self.assertFalse(f.is_javascript())
    self.assertFalse(f.is_css())

----------



Test Class Name: TestFiles