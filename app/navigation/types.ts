import type { NavigatorScreenParams } from '@react-navigation/native';

export type FriendsStackParamList = {
  FriendsList: undefined;
  FriendDetail: { daterId: string };
  FriendScout: { daterId: string };
};

export type WingerTabParamList = {
  Friends: NavigatorScreenParams<FriendsStackParamList>;
  Activity: undefined;
  Me: undefined;
};

export type MessagesStackParamList = {
  MessagesList: undefined;
  MessageThread: { matchId: string; otherName?: string; otherUserId?: string };
};

export type ProfileStackParamList = {
  ProfileHome: undefined;
  ProfileEdit: undefined;
  ProfileEditBasics: undefined;
  ProfileEditBio: undefined;
  ProfileEditInterests: undefined;
  ProfileEditLookingFor: undefined;
  ProfileEditPhotos: undefined;
  ProfileEditPrompts: undefined;
  WingpeopleList: undefined;
  WingpeopleContribute: { daterId: string };
  WingpeopleWingswipe: { daterId: string };
};

export type DaterTabParamList = {
  Discover: undefined;
  Matches: undefined;
  Messages: NavigatorScreenParams<MessagesStackParamList>;
  Profile: NavigatorScreenParams<ProfileStackParamList>;
};

// Flat, app-wide screen list — every leaf/container screen in the tree, keyed
// once. Registered globally below so any useNavigation()/navigate() call
// anywhere is typed without generics, including cross-navigator jumps (e.g.
// navigate('DaterTabs', { screen: 'Profile', params: { screen: 'WingpeopleList' } })).
export type RootStackParamList = {
  Login: undefined;
  Onboarding: undefined;
  WingerTabs: NavigatorScreenParams<WingerTabParamList>;
  DaterTabs: NavigatorScreenParams<DaterTabParamList>;
  Invite: undefined;
  MagicLink: undefined;
  Settings: undefined;
} & WingerTabParamList &
  FriendsStackParamList &
  DaterTabParamList &
  MessagesStackParamList &
  ProfileStackParamList;

declare global {
  namespace ReactNavigation {
    interface RootParamList extends RootStackParamList {}
  }
}
