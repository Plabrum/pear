#import <React/RCTBridgeModule.h>

@interface RCT_EXTERN_MODULE(PearNotificationsModule, NSObject)

RCT_EXTERN_METHOD(isDevice
                   : (RCTPromiseResolveBlock)resolve reject
                   : (RCTPromiseRejectBlock)reject)

RCT_EXTERN_METHOD(requestAndRegister
                   : (RCTPromiseResolveBlock)resolve reject
                   : (RCTPromiseRejectBlock)reject)

@end
