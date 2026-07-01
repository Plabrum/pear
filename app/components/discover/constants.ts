import { Dimensions } from 'react-native';

export const PAGE_SIZE = 20;
export const SWIPE_THRESHOLD = 110;
export const SCREEN_WIDTH = Dimensions.get('window').width;

export type Filter = 'likes' | 'handpicked';
