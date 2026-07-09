import { createNativeStackNavigator } from '@react-navigation/native-stack';

import type { ProfileStackParamList } from './types';
import ProfileHomeScreen from '../app/(tabs)/profile/index';
import ProfileEditScreen from '../app/(tabs)/profile/edit';
import ProfileEditBasicsScreen from '../app/(tabs)/profile/edit/basics';
import ProfileEditBioScreen from '../app/(tabs)/profile/edit/bio';
import ProfileEditInterestsScreen from '../app/(tabs)/profile/edit/interests';
import ProfileEditLookingForScreen from '../app/(tabs)/profile/edit/looking-for';
import ProfileEditPhotosScreen from '../app/(tabs)/profile/edit/photos';
import ProfileEditPromptsScreen from '../app/(tabs)/profile/edit/prompts';
import WingpeopleListScreen from '../app/(tabs)/profile/wingpeople/index';
import WingpeopleContributeScreen from '../app/(tabs)/profile/wingpeople/contribute';
import WingpeopleWingswipeScreen from '../app/(tabs)/profile/wingpeople/wingswipe';

const Stack = createNativeStackNavigator<ProfileStackParamList>();

export function ProfileStackNavigator() {
  return (
    <Stack.Navigator screenOptions={{ headerShown: false }}>
      <Stack.Screen name="ProfileHome" component={ProfileHomeScreen} />
      <Stack.Screen name="ProfileEdit" component={ProfileEditScreen} />
      <Stack.Screen name="ProfileEditBasics" component={ProfileEditBasicsScreen} />
      <Stack.Screen name="ProfileEditBio" component={ProfileEditBioScreen} />
      <Stack.Screen name="ProfileEditInterests" component={ProfileEditInterestsScreen} />
      <Stack.Screen name="ProfileEditLookingFor" component={ProfileEditLookingForScreen} />
      <Stack.Screen name="ProfileEditPhotos" component={ProfileEditPhotosScreen} />
      <Stack.Screen name="ProfileEditPrompts" component={ProfileEditPromptsScreen} />
      <Stack.Screen name="WingpeopleList" component={WingpeopleListScreen} />
      <Stack.Screen name="WingpeopleContribute" component={WingpeopleContributeScreen} />
      <Stack.Screen name="WingpeopleWingswipe" component={WingpeopleWingswipeScreen} />
    </Stack.Navigator>
  );
}
