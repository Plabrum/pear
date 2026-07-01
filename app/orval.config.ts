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
        operations: {
          // The swipe feed is the one cursor-paginated surface — emit infinite
          // hooks for it so the deck pages via fetchNextPage instead of a
          // hand-rolled offset/loadMore loop. `pageOffset` is the cursor param.
          getApiDatingProfilesSwipe: {
            query: {
              useInfinite: true,
              useSuspenseInfiniteQuery: true,
              useInfiniteQueryParam: 'pageOffset',
            },
          },
        },
      },
      clean: true,
    },
    hooks: {
      afterAllFilesWrite: 'prettier --write',
    },
  },
});
