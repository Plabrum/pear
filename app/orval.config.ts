import { defineConfig } from 'orval';

export default defineConfig({
  pear: {
    input: { target: './openapi.json' },
    output: {
      mode: 'tags-split',
      target: './lib/api/generated',
      schemas: './lib/api/generated/model',
      client: 'react-query',
      httpClient: 'fetch',
      baseUrl: '',
      override: {
        mutator: {
          path: './lib/api/http.ts',
          name: 'pearFetch',
        },
        fetch: {
          includeHttpResponseReturnType: false,
        },
        query: {
          useQuery: false,
          useSuspenseQuery: true,
          signal: true,
        },
      },
      clean: true,
    },
    hooks: {
      afterAllFilesWrite: 'prettier --write',
    },
  },
});
