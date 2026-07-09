import { createNativeStackNavigator } from '@react-navigation/native-stack';

import type { ProfileStackParamList } from './types';
import ProfileHomeScreen from '../features/profile/index';
import ProfileEditScreen from '../features/profile/edit';
import ProfileEditBasicsScreen from '../features/profile/edit/basics';
import ProfileEditBioScreen from '../features/profile/edit/bio';
import ProfileEditInterestsScreen from '../features/profile/edit/interests';
import ProfileEditLookingForScreen from '../features/profile/edit/looking-for';
import ProfileEditPhotosScreen from '../features/profile/edit/photos';
import ProfileEditPromptsScreen from '../features/profile/edit/prompts';
import WingpeopleListScreen from '../features/wingpeople/index';
import WingpeopleContributeScreen from '../features/wingpeople/contribute';
import WingpeopleWingswipeScreen from '../features/wingpeople/wingswipe';

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
