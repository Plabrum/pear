#import <React/RCTBridgeModule.h>

@interface RCT_EXTERN_MODULE(PearAppleAuthModule, NSObject)

RCT_EXTERN_METHOD(signIn
                   : (RCTPromiseResolveBlock)resolve reject
                   : (RCTPromiseRejectBlock)reject)

@end
